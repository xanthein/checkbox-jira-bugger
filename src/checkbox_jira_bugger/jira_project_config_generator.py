#!/usr/bin/python3
import git
import os
import logging
import json
import glob
import sys

"""
JiraProjectConfigGenerator.py

This module generates a Jira project configuration file by processing hardware
information JSON files from the oem-hw-info repository. It extracts metabug
information from JSON files in platform-specific directories and generates
a consolidated Jira project configuration.

The module:
1. Clones/updates the oem-hw-info repository
2. Processes JSON files from specified platform directories (stella, somerville, sutton)
3. Only includes files with specified series prefixes (e.g., "numbat-")
4. Generates a consolidated jira_project_config.json file

Usage:
    python JiraProjectConfigGenerator.py

Git access configuration:
# Here is the ssh configuration needed in the BH server.
# 1. ~/.ssh/config
#   Host lp_git_use_bot_account
#     HostName git.launchpad.net
#     User oem-taipei-bot
#     IdentityFile ~/.ssh/oem-taipei-bot/id_rsa
# 2. put bot's id_rsa into ~/.ssh/oem-taipei-bot/
"""

# Hardware info repository configuration
HW_INFO_REPO = "git+ssh://lp_git_use_bot_account/~oem-solutions-engineers/oem-dev-tools/+git/oem-hw-info"
BH_DEFAULT_JIRA_PROJECT_CONF_PATH = "~/.checkbox-jira-bugger/jira_project_config"
HW_INFO_LOCAL_PATH = os.path.join(
    os.path.expanduser(BH_DEFAULT_JIRA_PROJECT_CONF_PATH), "oem-hw-info"
)

PLATFORM_INFO_BASE = os.path.join(HW_INFO_LOCAL_PATH, "platform-info")
PLATFORM_PATHS = [
    os.path.join(PLATFORM_INFO_BASE, "stella"),
    os.path.join(PLATFORM_INFO_BASE, "somerville"),
    os.path.join(PLATFORM_INFO_BASE, "sutton"),
]
ALLOWED_SERIES = ["numbat"]  # TODO: add more series when supported
OUTPUT_CONFIG_PATH = os.path.join(
    os.path.expanduser(BH_DEFAULT_JIRA_PROJECT_CONF_PATH), "jira_project_config.json"
)

EXCEPTION_PROJECT_CARD = ["DELTA"]  # Jira Project Ticket exists, but not in oem-hw-info


def clone_or_pull_hw_info():
    """Clone or pull the hardware info repository"""
    logging.info("Ensuring hardware info repository is up to date...")

    try:
        if not os.path.exists(HW_INFO_LOCAL_PATH):
            logging.info("Cloning hardware info repository...")
            git.Repo.clone_from(HW_INFO_REPO, HW_INFO_LOCAL_PATH)
            logging.info("Hardware info repository cloned successfully")
        else:
            logging.info("Pulling latest hardware info...")
            repo = git.Repo(HW_INFO_LOCAL_PATH)
            origin = repo.remotes.origin
            origin.pull()
            logging.info("Hardware info repository updated successfully")
    except Exception as e:
        logging.error(f"Error managing hardware info repository: {str(e)}")
        raise


class JiraConfigGenerator:
    def __init__(self, allowed_series=ALLOWED_SERIES):
        self.config_data = {"OEM_X86_JIRA_CONF": {}}
        self.allowed_series = allowed_series

    def _get_project_from_path(self, platform_info_path):
        """Extract project name from platform info path"""
        return os.path.basename(platform_info_path)

    def _get_component_from_filename(self, filename):
        """Extract component name from the JSON filename"""
        # Remove .json extension and return the base name
        return os.path.splitext(os.path.basename(filename))[0]

    def _is_allowed_series(self, component_name):
        """Check if the component name starts with an allowed series prefix"""
        return any(
            component_name.startswith(f"{series}-") for series in self.allowed_series
        )

    def _parse_json_file(self, filepath, project):
        """Parse a single JSON file and extract metabug info"""
        try:
            component = self._get_component_from_filename(filepath)

            # Skip if component doesn't start with allowed series
            if not self._is_allowed_series(component):
                logging.debug(
                    f"Skipping {filepath} - series not in allowed list: {self.allowed_series}"
                )
                return None

            with open(filepath, "r") as f:
                data = json.load(f)
                if "metabug" not in data:
                    logging.warning(f"Missing metabug field in {filepath}")
                    return None

                logging.info(
                    f"Processing config for component {component} in project {project}"
                )
                logging.debug(
                    f"Metabug data from {filepath}: {json.dumps(data['metabug'], indent=2)}"
                )
                jira_card = str(
                    data["metabug"]
                )  # Convert to string to handle integer values from LP bugs
                if jira_card.split("-")[0].upper() in EXCEPTION_PROJECT_CARD:
                    # Jira Ticket does not have dedicated project directory in oem-hw-info
                    # so use the project name of the Jira card itself
                    # e.g DELTA SKUs are under oem-hw-info/somerville
                    project = jira_card.split("-")[0].lower()
                elif not jira_card.upper().startswith(project.upper()):
                    logging.warning(
                        f"Metabug '{jira_card}' in {filepath} doesn't start with project name '{project}'"
                    )
                    return None

                return {
                    "project": project,
                    "component": component,
                    "jira_card": jira_card,
                }
        except Exception as e:
            logging.error(f"Error parsing {filepath}: {str(e)}")
            return None

    def _add_component_to_project(self, project_name, component_name, jira_card):
        """Add a component entry to a project in the config data"""
        if project_name not in self.config_data["OEM_X86_JIRA_CONF"]:
            self.config_data["OEM_X86_JIRA_CONF"][project_name] = {
                "jira_project": project_name.upper(),
                "jira_components": [],
            }

        # Add component if it doesn't exist
        project_data = self.config_data["OEM_X86_JIRA_CONF"][project_name]
        component_exists = any(
            comp["component_name"] == component_name
            for comp in project_data["jira_components"]
        )

        if not component_exists:
            project_data["jira_components"].append(
                {
                    "component_name": component_name,
                    "jira_enable_platform_card": jira_card,
                }
            )

    def generate_config_for_project(self, platform_info_path):
        """Generate config for a specific project's platform info directory"""
        if not os.path.exists(platform_info_path):
            logging.error(f"Platform info path does not exist: {platform_info_path}")
            return

        project = self._get_project_from_path(platform_info_path)
        json_pattern = os.path.join(platform_info_path, "*.json")
        json_files = glob.glob(json_pattern)

        for json_file in json_files:
            data = self._parse_json_file(json_file, project)
            if data:
                self._add_component_to_project(
                    data["project"], data["component"], data["jira_card"]
                )

    def save_config(self, output_path):
        """Save the generated config to a file"""
        try:
            logging.info(f"Preparing to save config to {output_path}")
            # Create the directory if it doesn't exist
            output_dir = os.path.dirname(output_path)
            os.makedirs(output_dir, exist_ok=True)

            # Sort the data before saving
            sorted_data = {"OEM_X86_JIRA_CONF": {}}

            project_names = sorted(self.config_data["OEM_X86_JIRA_CONF"].keys())
            logging.debug(f"Sorting config for projects: {project_names}")

            # Process each project in sorted order
            for project_name in project_names:
                project_data = self.config_data["OEM_X86_JIRA_CONF"][project_name]
                logging.debug(f"Processing project {project_name}")

                # Sort components by component_name
                sorted_components = sorted(
                    project_data["jira_components"], key=lambda x: x["component_name"]
                )

                sorted_data["OEM_X86_JIRA_CONF"][project_name] = {
                    "jira_project": project_data["jira_project"],
                    "jira_components": sorted_components,
                }

            logging.debug(f"Final sorted config: {json.dumps(sorted_data, indent=2)}")
            with open(output_path, "w") as f:
                json.dump(sorted_data, f, indent=4)
                f.write("\n")
            logging.info(f"Config file successfully saved to {output_path}")
        except Exception as e:
            logging.error(f"Error saving config file: {str(e)}")


def generate_jira_config():
    """Generate the Jira config file using predefined settings"""
    logging.info("Starting Jira project config generation")

    # Ensure the hardware info repo is up to date
    clone_or_pull_hw_info()
    generator = JiraConfigGenerator()

    # Process each platform info directory
    for platform_path in PLATFORM_PATHS:
        generator.generate_config_for_project(platform_path)

    # Save the combined config
    generator.save_config(OUTPUT_CONFIG_PATH)

    logging.info("Jira project config generation completed")


def main():
    # Only set up logging if it hasn't been configured already
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
        )

    try:
        generate_jira_config()

        logging.info("Jira configuration file generation completed successfully")
    except Exception as e:
        logging.error(f"Error generating Jira config: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
