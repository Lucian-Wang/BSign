"""Deployment configuration tests; no Docker daemon or network required."""
import base64
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('configure', Path(__file__).resolve().parents[1]/'deploy/configure.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Deployment(unittest.TestCase):
    def test_new_install_and_repeat_preserve_secrets(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            self.assertTrue(module.configure(root, 'sign.example.com', 'ops@example.com', 'admin@example.com', False))
            initial = (root/'.env.production').read_bytes()
            values = dict(line.split('=', 1) for line in initial.decode().splitlines())
            self.assertEqual(len(base64.b64decode(values['BSIGN_MASTER_KEY'])), 32)
            self.assertGreaterEqual(len(values['BSIGN_BOOTSTRAP_TOKEN']), 40)
            self.assertFalse(module.configure(root, 'sign.example.com', 'ops@example.com', 'admin@example.com', False))
            self.assertEqual(initial, (root/'.env.production').read_bytes())
            with self.assertRaises(ValueError):
                module.configure(root, 'other.example.com', 'ops@example.com', 'admin@example.com', False)
            self.assertEqual(initial, (root/'.env.production').read_bytes())

    def test_invalid_inputs_write_nothing(self):
        for domain, email in [('https://sign.example.com', 'a@example.com'), ('example.com;id', 'a@example.com'), ('example.com', 'a@example.com\nINJECT=yes')]:
            with tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                with self.assertRaises(ValueError):
                    module.configure(root, domain, email, 'admin@example.com', False)
                self.assertEqual(list(root.iterdir()), [])

    def test_partial_or_corrupt_configuration_is_not_replaced(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            module.configure(root, 'sign.example.com', 'ops@example.com', 'admin@example.com', True)
            private = root/'.env.production'
            text = private.read_text()
            private.write_text(text.replace(next(line for line in text.splitlines() if line.startswith('BSIGN_MASTER_KEY=')), 'BSIGN_MASTER_KEY=bad'))
            corrupt = private.read_bytes()
            with self.assertRaises(ValueError):
                module.configure(root, 'sign.example.com', 'ops@example.com', 'admin@example.com', True)
            self.assertEqual(private.read_bytes(), corrupt)
            (root/'.env.deploy').unlink()
            with self.assertRaises(ValueError):
                module.configure(root, 'sign.example.com', 'ops@example.com', 'admin@example.com', True)


if __name__ == '__main__':
    unittest.main()
