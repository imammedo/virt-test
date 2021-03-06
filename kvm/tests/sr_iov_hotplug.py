import re, logging
from autotest.client.shared import error
from virttest import utils_misc, aexpect, utils_test

@error.context_aware
def run_sr_iov_hotplug(test, params, env):
    """
    Test hotplug of sr-iov devices.

    (Elements between [] are configurable test parameters)
    1) Set up sr-iov test environment in host.
    2) Start VM.
    3) PCI add one/multi sr-io  deivce with (or without) repeat
    4) Compare output of monitor command 'info pci'.
    5) Compare output of guest command [reference_cmd].
    6) Verify whether pci_model is shown in [pci_find_cmd].
    7) Check whether the newly added PCI device works fine.
    8) Delete the device, verify whether could remove the sr-iov device.

    @param test:   KVM test object.
    @param params: Dictionary with the test parameters.
    @param env:    Dictionary with test environment.
    """


    def pci_add_iov(pci_num):
        pci_add_cmd = ("pci_add pci_addr=auto host host=%s,if=%s" %
                       (pa_pci_ids[pci_num], pci_model))
        if params.get("hotplug_params"):
            assign_param = params.get("hotplug_params").split()
            for param in assign_param:
                value = params.get(param)
                if value:
                    pci_add_cmd += ",%s=%s" % (param, value)

        return pci_add(pci_add_cmd)

    def pci_add(pci_add_cmd):
        error.context("Adding pci device with command 'pci_add'")
        add_output = vm.monitor.send_args_cmd(pci_add_cmd, convert=False)
        pci_info.append(['' , add_output])

        if not "OK domain" in add_output:
            raise error.TestFail("Add PCI device failed. "
                                 "Monitor command is: %s, Output: %r" %
                                 (pci_add_cmd, add_output))
        return  vm.monitor.info("pci")

    def check_support_device(dev):
        if is_qmp_monitor:
            devices_supported = vm.monitor.human_monitor_cmd("%s ?" % cmd_type)
        else:
            devices_supported = vm.monitor.send_args_cmd("%s ?" % cmd_type)
        # Check if the device is support in qemu
        is_support = utils_test.find_substring(devices_supported, dev)
        if not is_support:
            raise error.TestError("%s doesn't support device: %s" %
                                  (cmd_type, dev))


    def device_add_iov(pci_num):
        device_id = "%s" % pci_model + "-" + utils_misc.generate_random_id()
        pci_info.append([device_id])
        check_support_device("pci-assign")
        pci_add_cmd = ("device_add id=%s,driver=pci-assign,host=%s" %
                       (pci_info[pci_num][0], pa_pci_ids[pci_num]))
        if params.get("hotplug_params"):
            assign_param = params.get("hotplug_params").split()
            for param in assign_param:
                value = params.get(param)
                if value:
                    pci_add_cmd += ",%s=%s" % (param, value)
        return device_add(pci_num, pci_add_cmd)

    def device_add(pci_num, pci_add_cmd):
        error.context("Adding pci device with command 'device_add'")
        if is_qmp_monitor:
            add_output = vm.monitor.send_args_cmd(pci_add_cmd)
        else:
            add_output = vm.monitor.send_args_cmd(pci_add_cmd, convert=False)
        pci_info[pci_num].append(add_output)

        after_add = vm.monitor.info("pci")
        if pci_info[pci_num][0] not in after_add:
            logging.debug("Print info pci after add the block: %s" % after_add)
            raise error.TestFail("Add device failed. Monitor command is: %s"
                                 ". Output: %r" % (pci_add_cmd, add_output))
        return after_add

    # Hot add a pci device
    def add_device(pci_num):
        reference_cmd = params.get("reference_cmd")
        find_pci_cmd = params.get("find_pci_cmd")
        info_pci_ref = vm.monitor.info("pci")
        reference = session.cmd_output(reference_cmd)

        try:
            # get function for adding device.
            add_fuction = local_functions["%s_iov" % cmd_type]
        except Exception:
            raise error.TestError("No function for adding sr-iov dev with '%s'" %
                                  cmd_type)
        after_add = None
        if add_fuction:
            # Do add pci device.
            after_add = add_fuction(pci_num)

        try:
            # Define a helper function to compare the output
            def _new_shown():
                o = session.cmd_output(reference_cmd)
                return o != reference

            # Define a helper function to catch PCI device string
            def _find_pci():
                o = session.cmd_output(find_pci_cmd)
                if re.search(match_string, o, re.IGNORECASE):
                    return True
                else:
                    return False

            error.context("Start checking new added device")
            # Compare the output of 'info pci'
            if after_add == info_pci_ref:
                raise error.TestFail("No new PCI device shown after executing "
                                     "monitor command: 'info pci'")

            secs = int(params.get("wait_secs_for_hook_up"))
            if not utils_misc.wait_for(_new_shown, test_timeout, secs, 3):
                raise error.TestFail("No new device shown in output of command "
                                     "executed inside the guest: %s" %
                                     reference_cmd)

            if not utils_misc.wait_for(_find_pci, test_timeout, 3, 3):
                raise error.TestFail("New add sr-iov device not found in guest. "
                                     "Command was: %s" % find_pci_cmd)

            # Test the newly added device
            try:
                session.cmd(params.get("pci_test_cmd") % (pci_num+1))
            except aexpect.ShellError, e:
                raise error.TestFail("Check for sr-iov device failed after PCI "
                                     "hotplug. Output: %r" % e.output)

        except Exception:
            pci_del(pci_num, ignore_failure=True)
            raise

    # Hot delete a pci device
    def pci_del(pci_num, ignore_failure=False):
        def _device_removed():
            after_del = vm.monitor.info("pci")
            return after_del != before_del

        before_del = vm.monitor.info("pci")
        if cmd_type == "pci_add":
            slot_id = "0" + pci_info[pci_num][1].split(",")[2].split()[1]
            cmd = "pci_del pci_addr=%s" % slot_id
            vm.monitor.send_args_cmd(cmd, convert=False)
        elif cmd_type == "device_add":
            cmd = "device_del id=%s" % pci_info[pci_num][0]
            vm.monitor.send_args_cmd(cmd)

        if (not utils_misc.wait_for(_device_removed, test_timeout, 0, 1)
            and not ignore_failure):
            raise error.TestFail("Failed to hot remove PCI device: %s. "
                                 "Monitor command: %s" %
                                 (pci_model, cmd))


    vm = env.get_vm(params["main_vm"])
    vm.verify_alive()
    timeout = int(params.get("login_timeout", 360))
    session = vm.wait_for_login(timeout=timeout)

    test_timeout = int(params.get("test_timeout", 360))
    # Test if it is nic or block
    pci_num_range = int(params.get("pci_num", 1))
    rp_times = int(params.get("repeat_times", 1))
    pci_model = params.get("pci_model", "pci-assign")
    # Need udpate match_string if you use a card other than 82576
    match_string = params.get("match_string", "82576")
    if vm.pci_assignable is not None:
        pa_pci_ids = vm.pci_assignable.request_devs(pci_num_range)

    # Modprobe the module if specified in config file
    module = params.get("modprobe_module")
    if module:
        error.context("modprobe the module %s" %module, logging.info)
        session.cmd("modprobe %s" % module)

    # check monitor type
    qemu_binary = params.get("qemu_binary", "/usr/bin/qemu-kvm")
    qemu_binary = utils_misc.get_path(test.bindir, qemu_binary)
    is_qmp_monitor = (utils_misc.qemu_has_option("qmp", qemu_binary)
                     and params.get("monitor_type") == "qmp")
    # Probe qemu to verify what is the supported syntax for PCI hotplug
    if is_qmp_monitor:
        cmd_o = vm.monitor.info("commands")
    else:
        cmd_o = vm.monitor.send_args_cmd("help")

    cmd_type = utils_test.find_substring(str(cmd_o), "device_add", "pci_add")
    if not cmd_o:
        raise error.TestError("Unknow version of qemu")


    local_functions = locals()

    for j in range(rp_times):
        # pci_info is a list of list.
        # each element 'i' has 4 members:
        # pci_info[i][0] == device id, only used for device_add
        # pci_info[i][1] == output of device add command
        pci_info = []
        for pci_num in xrange(pci_num_range):
            msg = "Start hot-adding %sth pci device, repeat %d" % (pci_num + 1,
                                                                  j + 1)
            error.context(msg, logging.info)
            add_device(pci_num)
        for pci_num in xrange(pci_num_range):
            msg = "start hot-deleting %sth pci device repeat %d" % (pci_num + 1,
                                                                    j + 1)
            error.context(msg, logging.info)
            pci_del(-(pci_num + 1))
