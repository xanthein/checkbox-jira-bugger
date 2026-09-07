"""Checkbox submission report parsing.

Ported from BugHamster/BugHamsterCommon.py (bughamster repo). Pure parsing
and file-extraction helpers only -- no Launchpad or Jira dependency.
"""
import json
import logging
import os
import re
import shutil
import tarfile
import tempfile
from datetime import datetime

# test category to HWE tag mapping table
tag_mapping_table = {
    'audio': 'hwe-audio',
    'benchmarks': 'hwe-banchmarks',
    'bluetooth': 'hwe-bluetooth',
    'camera': 'hwe-camera',
    'cpu': 'hwe-cpu',
    'disk': 'hwe-media',
    'ethernet': 'hwe-networking-ethernet',
    'firmware': 'hwe-firmware',
    'graphics': 'hwe-graphics',
    'input': 'hwe-input',
    'memory': 'hwe-memory',
    'mobilebroadband': 'hwe-mobilebroadband',
    'optical': 'hwe-media',
    'power-management': 'hwe-powermanagement',
    'suspend': 'hwe-suspend-resume',
    'touchpad': 'hwe-touchpad',
    'tpm2.0_4.1.1': 'hwe-tpm',
    'clevis-encrypt-tpm2': 'hwe-tpm',
    'usb': 'hwe-usb',
    'wireless': 'hwe-networking-wifi',
    'after-suspend-wireless': 'hwe-networking-wifi'
}

BUG_TITLE_TEMPLATE = '''[Sanity] {test_id} failed'''

# NOTE: every meaningful line below is separated by a BLANK line (double
# newline), not a single "\n". This is required, not cosmetic: confirmed
# against a real Jira Cloud issue (STELLA-4127), Jira's storage layer
# silently drops a single "\n" line break with zero separator (not even a
# space), merging adjacent lines together -- only a blank line survives,
# converted to a real line break (rendered back as a single "\n" when read
# via the v2/string API). Without the blank lines, fields like "SKU:" and
# "BIOS ID:" get jammed onto one unparseable line once Jira stores the bug.
BUG_DESCRIPTION_TEMPLATE = '''
[Summary]

{test_id} failed

certification_status: {certification_status}

[I/O log]

{test_iolog}

[Reproduce Steps]

1. sudo checkbox-cli run {test_full_id}

[Results]

failed

[Additional Information]

Manifest: {manifest_name} {manifest_version}

BIOS Version: {bios_version}

SKU: {sku_name}

BIOS ID: {sku_number}

Tester: {tester}
'''

USN_BUFFER_DAYS = 7


def is_valid_sku_name(sku_name):
    """
    e.g. OAS4-DVT2-ODM_202403-33541
    """
    skuname_reg = re.compile(r'.*_\d{6}-\d{5}$')
    ret = skuname_reg.match(sku_name)
    if ret:
        return True
    else:
        return False


def get_hwe_tag(bug_title):
    if '/' in bug_title:
        clean_title = bug_title[bug_title.find(']') + 1:]  # remove [Sanity] prefix
        test_category = clean_title.split('/')[0].strip()
        try:
            logging.info('mapping {}-->{}'.format(test_category, tag_mapping_table[test_category]))
            return tag_mapping_table[test_category]
        except KeyError:
            logging.info('mapping {}-->{}'.format(test_category, 'tag undefine'))
            return None


def get_ubuntu_version(submission_jsondata):
    ubuntu_version_reg = re.compile(r'\d{2}.\d{2}')
    for item in submission_jsondata['attachment-results']:
        if item['id'] == 'system_info_json':
            if item['status'] == 'fail':
                logging.info('attachment_id: system_info_json failed, \
                             can not get Ubuntu version information!')
            else:
                logging.info('Ubuntu version info: %s' % item['io_log'])
                system_info_string = item['io_log']
            break
    system_info_json = json.loads(system_info_string)
    for i in system_info_json['System']:
        if "Distro" in i:
            system_string = i
            break
    for j in i.split():
        ret = ubuntu_version_reg.match(j)
        if ret:
            print(ret.group(0))
            return ret.group(0)

    return ""


def get_ubuntu_distro_version(submission_jsondata):
    """
    Read system_info_json io_log
    Return ubuntu version in float
    e.g.
    {
    "System": [
        "Kernel: 6.8.0-31-generic x86_64",
        "Distro: Ubuntu 24.04 LTS (Noble Numbat)"]
    ...
    """
    for item in submission_jsondata['attachment-results']:
        if item['id'] == 'system_info_json':
            if item['status'] in ["fail", "skip"]:
                logging.info('attachment_id: system_info_json failed, \
                             can not get Ubuntu Distro information!')
                return None
            else:
                #logging.info('system_info_json: %s' % item['io_log'])
                sys_info_json = json.loads(item['io_log'])
                for i in sys_info_json['System']:
                    if "Distro" in i:
                        ret = re.findall(r'\d{2}.\d{2}', i, flags=re.IGNORECASE)[0]
                        return float(ret)


def read_bto_version(submission_jsondata):
    for item in submission_jsondata['attachment-results']:
        if item['id'] == 'recovery_info_attachment':
            print(item['status'])
            if item['status'] in ["fail", "skip"]:
                logging.info('attachment_id: recovery_info_attachment failed, \
                             can not get manifest information!')
                print(get_ubuntu_distro_version(submission_jsondata))
            else:
                logging.info('manifest info: %s' % item['io_log'])
                image_info = item['io_log']
    logging.debug('get_manifest_version: %s' % image_info)
    platform_image_info = image_info.split('bto_version:')[1]
    manifest_name = platform_image_info.split()[0]
    manifest_version = platform_image_info.split()[1]
    logging.debug('manifest_name: %s' % manifest_name)
    logging.debug('manifest_version: %s' % manifest_version)
    return manifest_name, manifest_version


def get_manifest_and_device_information_from_file(submission_tarball):
    submission_dir = extract_submission_tarball(submission_tarball)
    if submission_dir is None:
        return False

    logging.debug('submission_dir %s' % submission_dir)

    with open(os.path.join(submission_dir, 'submission.json'), 'rb') as fobj:
        data = json.load(fobj)

    # Return manifest_name, manifest_version, bios_version, sku_number
    return get_manifest_and_device_information(data)


def get_manifest_and_device_information(submission_jsondata):
    '''
    buildstamp format example:
        somerville:
            "buildstamp": "canonical-oem-somerville-focal-amd64-20200502-85+fossa-proposed-release+X94"
        sutton:
            "buildstamp": "sutton-newell-focal-amd64-20201111-122"
        stella:
            "buildstamp": "pc-stella-cmit-focal-amd64-X00-20201126-1146"

    bios_version (raw-devices-dmi/bios_version):
    sku_number (raw-devices-dmi/system_sku):
    '''
    manifest_name = 'unknown'
    manifest_version = 'unknown'
    bios_version = 'unknown'
    sku_number = 'unknown'
    image_info = 'unknown'
    try:
        image_info = submission_jsondata['buildstamp']
    except Exception:
        logging.warning('Can not find buildstamp in submission!')
        return manifest_name, manifest_version, bios_version, sku_number

    logging.debug('buildstamp: %s' % image_info)

    ubuntu_version = get_ubuntu_distro_version(submission_jsondata)

    if ubuntu_version > float(22.04):
        #  ubuntu version >= 24.04, buildstamp format is  "canonical-oem-somerville-noble-hwe-20240506-69" 
        # return "canonical-oem-somerville-noble-hwe" as manifest name
        # return "20240506-69" as manifest version
        manifest_version = re.findall(r'\d{8}-\d{1,4}', image_info, flags=re.IGNORECASE)[0]
        manifest_name = image_info.replace("-" + manifest_version, "")
    else:
        # Below logic is for ubuntu distro <= 22.04
        if image_info != 'unknown':
            if 'somerville' in image_info:
                logging.info('submission comes from somerville image')
                if '+' in image_info:
                    manifest_name = image_info.split('+')[1]
                    manifest_version = image_info.split('+')[2]
                else:
                    # read image info from bto_version if buildstamp format incorrect
                    manifest_name, manifest_version = read_bto_version(submission_jsondata)
            else:
                logging.info('submission comes from sutton or stella oem image')
                try:
                    manifest_name = image_info
                    # maybe to be paranoid
                    # manifest_name = image_info.split('-' + manifest_version)[0]
                    manifest_version = re.search('[0-9]{8}-[0-9]{1,4}', image_info).group(0)
                except AttributeError:
                    manifest_version = ''
    logging.info('manifest_name: %s' % manifest_name)
    logging.info('manifest_version: %s' % manifest_version)

    for item in submission_jsondata['raw-devices-dmi']:
        if 'bios_version' in item:
            logging.debug('raw-devices-dmi: bios_version:%s' % item['bios_version'])
            bios_version = item['bios_version']
        if 'system_sku_number' in item:
            logging.debug('raw-devices-dmi: system_sku_number:%s' % item['system_sku_number'])
            sku_number = item['system_sku_number']
        if 'system_sku' in item:
            logging.debug('raw-devices-dmi: system_sku:%s' % item['system_sku'])
            sku_number = item['system_sku']

    return manifest_name, manifest_version, bios_version, sku_number


def format_bug(manifest_name, manifest_version, test_id, certification_status, test_iolog, test_full_id,
               bios_version, sku_number, sku_name, tester='oem-taipei-bot'):
    title = BUG_TITLE_TEMPLATE.format(test_id=test_id)
    description = BUG_DESCRIPTION_TEMPLATE.format(
        test_id=test_id,
        certification_status=certification_status,
        test_iolog=test_iolog,
        test_full_id=test_full_id,
        manifest_name=manifest_name,
        manifest_version=manifest_version,
        bios_version=bios_version,
        sku_number=sku_number,
        sku_name=sku_name,
        tester=tester)
    logging.info('========================[New Bug]==========================')
    logging.info(title)
    logging.info(description)
    logging.info('===========================================================')
    return title, description


def extract_submission_tarball(submission_tar_xz):
    tmpdir = tempfile.mkdtemp(prefix='sanity-bugmgr-submission-tmp-')
    logging.debug('tmpdir: %s' % tmpdir)
    try:
        with tarfile.open(submission_tar_xz) as f:
            f.extractall(path=tmpdir)
            return tmpdir
    except Exception:
        logging.warning('open file error: %s' % submission_tar_xz)


def clean_up(tmpdir):
    logging.debug('clean_up %s' % tmpdir)
    try:
        shutil.rmtree(tmpdir)
    except OSError as e:
        logging.warning(e)
        return


def setting_bug_importance(item, project_name):
    '''
    Somerville: all power management tests are critical
    Stella: keep cpu-low-power-idle and system-low-power-idle to high
    '''
    if item['certification_status'] == 'blocker':
        bug_importance = 'Critical'
    elif project_name == 'somerville' and 'power-management' in item['id']:
        bug_importance = 'Critical'
    else:
        bug_importance = 'High'
    return bug_importance


def usn_within_buffer_days(usn_info):
    '''
    Check if usn exceed bufffer days.
    '''
    usn_published_date = re.search(r'Published: (\d{1,2} \S+ \d{4})', usn_info).group(1)
    pdate_obj = datetime.strptime(usn_published_date, '%d %B %Y').date()
    today_obj = datetime.today().date()
    delta = today_obj - pdate_obj

    if delta.days <= USN_BUFFER_DAYS:
        return True
    else:
        return False


def get_exceeded_usn_list(cve_io_log):
    '''
    return list of usn which exceed buffer days.
    '''
    usn_list = re.findall(r'[UL]SN-\d{4,}-\d{1} -- .+\n\t- https://ubuntu.com/security/notices/[UL]SN-\d{4,}-\d{1}\n\t- \S+ Published: \d{1,2} \S+ \d{4}', cve_io_log)
    usn_within_buf = []
    usn_exceed_buf = []
    for i in usn_list:
        usn_i = re.search(r'([UL]SN-\d{4,}-\d{1}) --', i).group(1)
        if usn_within_buffer_days(i):
            logging.info('%s is within %s days' % (usn_i, USN_BUFFER_DAYS))
            usn_within_buf.append(usn_i)
        else:
            logging.info('%s is exceed %s days' % (usn_i, USN_BUFFER_DAYS))
            usn_exceed_buf.append(usn_i)
    return usn_exceed_buf, usn_within_buf


def apply_cve_buffer_rule(data):
    '''
    Apply cve buffer rule to test result
    '''
    i = 0
    for item in data['results']:
        if item['id'] == 'miscellanea/cvescan':
            usn_exceed_list, usn_within_list = get_exceeded_usn_list(item['io_log'])
            if len(usn_exceed_list):
                logging.info('CVE test failed! USN found and exceed %s days!' % USN_BUFFER_DAYS)
                data['results'][i]['status'] = 'fail'
                data['results'][i]['cve_append_message'] = 'USN exceed {} days:\n'.format(USN_BUFFER_DAYS) + '\n'.join('{}'.format(item) for item in usn_exceed_list)
            elif len(usn_within_list):
                logging.info('CVE test pass')
                data['results'][i]['status'] = 'pass'
                data['results'][i]['cve_append_message'] = 'USN within {} days:\n'.format(USN_BUFFER_DAYS) + '\n'.join('{}'.format(item) for item in usn_within_list)
            else:
                data['results'][i]['status'] = 'pass'
                data['results'][i]['cve_append_message'] = item['io_log']
            break
        i += 1


def get_chassis_type_from_submission(submission_dir):
    if submission_dir is None:
        return False

    logging.debug('submission_dir %s' % submission_dir)
    with open(os.path.join(submission_dir + '/attachment_files/', 'com.canonical.certification__dmi_attachment'), 'r') as fobj:
        data = fobj.readlines()
        for x in data:
            if 'chassis_type' in x:
                chassis_type_value = x.split(':', 1)
                chassis_type_value_hex = int(chassis_type_value[1], 10)
                logging.debug('0x%02x' % chassis_type_value_hex)
                return chassis_type_value_hex
