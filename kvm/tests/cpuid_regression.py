"""
Group of regression tests for cpuid
"""
import logging, re, sys, traceback, os
from autotest.client.shared import error, utils
from autotest.client.shared import test as test_module
from virttest import utils_misc, env_process


def run_cpuid_regression(test, params, env):
    """
    Boot guest with different cpu_models and cpu flags and check if guest works correctly.

    @param test: kvm test object.
    @param params: Dictionary with the test parameters.
    @param env: Dictionary with test environment.
    """
    qemu_binary = utils_misc.get_path('.', params.get("qemu_binary", "qemu"))


    def extract_qemu_cpu_models(qemu_cpu_help_text):
        """
        Get all cpu models from qemu -cpu help text.

        @param qemu_cpu_help_text: text produced by <qemu> -cpu ?
        @return: list of cpu models
        """

        cpu_re = re.compile("x86\s+\[?([a-zA-Z0-9_-]+)\]?.*\n")
        return cpu_re.findall(qemu_cpu_help_text)

    class MiniSubtest(test_module.Subtest):
        def __new__(cls, *args, **kargs):
            self = test.__new__(cls)
            ret = None
            if args is None:
                args = []
            try:
                ret = self.test(*args, **kargs)
            finally:
                if hasattr(self, "clean"):
                    self.clean()
            return ret

        def clean(self):
            if (hasattr(self, "vm")):
                vm = getattr(self, "vm")
                if vm.is_alive():
                    vm.pause()
                    vm.destroy(gracefully=False)

        def test(self):
            """
            stub for actual test code
            """
            raise error.TestFail("test() must be redifined in subtest")

    def print_exception(called_object):
        """
        print error including stack trace
        """
        exc_type, exc_value, exc_traceback = sys.exc_info()
        logging.error("In function (" + called_object.__name__ + "):")
        logging.error("Call from:\n" +
                      traceback.format_stack()[-2][:-1])
        logging.error("Exception from:\n" +
                      "".join(traceback.format_exception(
                                              exc_type, exc_value,
                                              exc_traceback.tb_next)))

    def get_guest_cpuid(self, cpu_model, feature=None):
        test_kernel_dir = os.path.join(test.virtdir, "deps", "cpuid_test_kernel")
        os.chdir(test_kernel_dir)
        utils.make("kernel.bin")

        vm_name = params.get('main_vm')
        params_b = params.copy()
        params_b["kernel"] = os.path.join(test_kernel_dir, "kernel.bin")
        params_b["cpu_model"] = cpu_model
        params_b["cpu_model_flags"] = feature
        del params_b["images"]
        del params_b["nics"]
        env_process.preprocess_vm(self, params_b, env, vm_name)
        vm = env.get_vm(vm_name)
        vm.create()
	self.vm = vm
        vm.resume()

        timeout = float(params.get("login_timeout", 240))
        f = lambda: re.search("==END TEST==", vm.serial_console.get_output())
        if not utils_misc.wait_for(f, timeout, 1):
            raise error.TestFail("Could not get test complete message.")

        test_sig = re.compile("==START TEST==\n((?:.*\n)*)\n*==END TEST==")
        test_output = test_sig.search(vm.serial_console.get_output())
        if test_output == None:
	    raise error.TestFail("Test output signature not found in "
                                 "output:\n %s", vm.serial_console.get_output())
        self.clean()
        return test_output.group(1)

    def cpuid_regs_to_dic(level_count, cpuid_dump):
        grp = '\w*=(\w*)\s*'
        regs = re.search('\s+%s:.*%s%s%s%s' % (level_count, grp, grp, grp, grp),
                         cpuid_dump)
	if regs == None:
            raise error.TestFail("Could not find %s in cpuid output",
                                 level_count)
        return {'eax': int(regs.group(1), 16), 'ebx': int(regs.group(2), 16),
                'ecx': int(regs.group(3), 16), 'edx': int(regs.group(4), 16) }

    def cpuid_to_vendor(cpuid_dump):
        r = cpuid_regs_to_dic('0x00000000 0x00', cpuid_dump)
        dst =  []
        map(lambda i: dst.append((chr(r['ebx'] >> (8 * i) & 0xff))), range(0,4))
        map(lambda i: dst.append((chr(r['edx'] >> (8 * i) & 0xff))), range(0,4))
        map(lambda i: dst.append((chr(r['ecx'] >> (8 * i) & 0xff))), range(0,4))
        return ''.join(dst)

    def cpuid_to_level(cpuid_dump):
        r = cpuid_regs_to_dic('0x00000000 0x00', cpuid_dump)
        return r['eax']

    class test_qemu_cpu_models_list(MiniSubtest):
        """
        check CPU models returned by <qemu> -cpu ? are what is expected
        """
        def test(self):
            """
            test method
            """
            if params.get("cpu_models") is None:
                raise error.TestFail("define cpu_models parameter to check "
                                     "verify supported CPU models list")

            cmd = qemu_binary + " -cpu ?"
            result = utils.run(cmd)

            qemu_models = extract_qemu_cpu_models(result.stdout)
            cpu_models = params.get("cpu_models").split()
            missing = set(cpu_models) - set(qemu_models)
            if missing:
                raise error.TestFail("CPU models %s are not in output "
                                     "'%s' of command \n%s" %
                                     (missing, cmd, result.stdout))
            added = set(qemu_models) - set(cpu_models)
            if added:
                raise error.TestFail("Unexpected CPU models %s are in output "
                                     "'%s' of command \n%s" %
                                     (added, cmd, result.stdout))

    class default_vendor(MiniSubtest):
        """
        Boot qemu with specified cpu models and
        verify that CPU vendor matches requested
        """
        def test(self):
            for cpu_model in params.get("cpu_models").split(' '):
                out = get_guest_cpuid(self, cpu_model)
                guest_vendor = cpuid_to_vendor(out)
                logging.debug("Guest's vendor: " + guest_vendor)
                if guest_vendor != params.get("vendor"):
                    raise error.TestFail("Guest vendor [%s], doen't match "
                                         "required vendor [%s] for CPU [%s]" %
                                         (guest_vendor, params.get("vendor"),
                                          cpu_model))

    class custom_vendor(MiniSubtest):
        """
        Boot qemu with specified vendor
        """
        def test(self):
            cpu_model = "qemu64"

            xfail = False
            if (params.get("xfail") is not None) and (params.get("xfail") == "yes"):
                xfail = True

            if params.get("cpu_model") is not None:
                cpu_model = params.get("cpu_model")

            if params.get("vendor") is None:
                raise error.TestFail("'vendor' must be specified in config"
                                     " for this test")
            vendor = params.get("vendor")

            try:
                out = get_guest_cpuid(self, cpu_model, "vendor=" + vendor)
                guest_vendor = cpuid_to_vendor(out)
                logging.debug("Guest's vendor: " + guest_vendor)
                if guest_vendor != params.get("vendor"):
                    raise error.TestFail("Guest vendor [%s], doen't match "
                                         "required vendor [%s] for CPU [%s]" %
                                         (guest_vendor, vendor, cpu_model))
            except:
               if xfail is False:
                   rise


    test_type = params.get("test_type")
    failed = []
    if test_type in locals():
        tests_group = locals()[test_type]
        try:
            tests_group()
        except:
            print_exception(tests_group)
            failed.append(test_type)
    else:
        raise error.TestFail("Test group '%s' is not defined in"
                             " test" % test_type)

    if failed != []:
        raise error.TestFail("Test of cpu models %s failed." %
                              (str(failed)))
