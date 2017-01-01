from unittest import TestCase
from ds import DS, extract, is_contains, ds_print


class TestDS(TestCase):
    def test_init(self):
        self.assertRaises(BaseException("init error"), DS.__init__, 'localhost', 'pavel', 'secret')

    def test_connect(self):
        ds = DS('localhost', 'pavel', 'secret')
        self.assertRaises(BaseException, ds.connect)

    def test_send(self):
        self.fail()

    def test_get_bof_primary(self):
        self.fail()

    def test_get_bof_secondary(self):
        self.fail()

    def test_get_config_primary(self):
        self.fail()

    def test_get_config_version(self):
        self.fail()

    def test_get_name(self):
        self.fail()

    def test_get_system_info(self):
        self.fail()

    def test_get_type(self):
        self.fail()

    def test_get_version(self):
        self.fail()

    def test_get_free_space(self):
        self.fail()

    def test_save_configuration(self):
        self.fail()

    def test_file_clear_readonly(self):
        self.fail()

    def test_file_copy(self):
        self.fail()

    def test_get_file_version(self):
        self.fail()

    def test_get_file_type(self):
        self.fail()

    def test_set_bof_primary(self):
        self.fail()

    def test_set_bof_secondary(self):
        self.fail()

    def test_make_health_check(self):
        self.fail()

    def test_make_check(self):
        self.fail()

    def test_file_is_exist(self):
        self.fail()

    def test_get_file_size(self):
        self.fail()

    def test__get_scp_client(self):
        self.fail()

    def test_scp_get_file(self):
        self.fail()

    def test_scp_put_file(self):
        self.fail()

    def test_file_delete(self):
        self.fail()

    def test_directory_delete(self):
        self.fail()
