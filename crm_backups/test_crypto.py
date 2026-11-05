"""Ключ владельца, аутентификация, порча и ограниченная память потока."""
import io
import unittest

from .crypto import generate_keys, encrypt, decrypt, public_id


class BoundedReader(io.BytesIO):
    def read(self, size=-1):
        if not 0 <= size <= 1024 * 1024:
            raise AssertionError('Неограниченное чтение архива')
        return super().read(size)


class ArchiveCryptoTests(unittest.TestCase):
    def setUp(self):
        self.private, self.public = generate_keys(b'owner-only-passphrase')

    def encoded(self, data=b'secret database and files'):
        output = io.BytesIO()
        encrypt(BoundedReader(data), output, self.public)
        return output.getvalue()

    def test_streaming_roundtrip_and_key_id(self):
        data = b'a test block' * 300000
        encoded = self.encoded(data)
        output = io.BytesIO()
        header = decrypt(BoundedReader(encoded), output, self.private, b'owner-only-passphrase')
        self.assertEqual(output.getvalue(), data)
        self.assertEqual(header['key_id'], public_id(self.public))
        self.assertNotIn(b'secret database', encoded)

    def test_wrong_key_password_tamper_and_truncation(self):
        other, _ = generate_keys(b'owner-only-passphrase')
        encoded = self.encoded()
        for private, password, blob in (
            (other, b'owner-only-passphrase', encoded),
            (self.private, b'wrong', encoded),
            (self.private, b'owner-only-passphrase', encoded[:-1]),
            (self.private, b'owner-only-passphrase', encoded[:-20] + b'X' + encoded[-19:]),
            (self.private, b'owner-only-passphrase', b'corrupt header'),
        ):
            with self.subTest(length=len(blob)), self.assertRaises(ValueError):
                decrypt(BoundedReader(blob), io.BytesIO(), private, password)

    def test_new_randomness_for_every_archive(self):
        self.assertNotEqual(self.encoded(), self.encoded())

    def test_unencrypted_owner_key_is_refused(self):
        with self.assertRaises(ValueError):
            generate_keys(b'')
