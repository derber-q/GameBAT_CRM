"""Потоковый контейнер v1: X25519 + HKDF-SHA256 + AES-256-GCM.

Только публичный ключ нужен серверу. Приватный ключ владельца — зашифрованный
PKCS8. Неаутентифицированный открытый текст никогда не возвращается вызывающему.
"""
import base64
import hashlib
import json
import os
import struct
import tempfile

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

MAGIC = b'RESOURCE-BACKUP-1\n'
BLOCK = 1024 * 1024


def generate_keys(password):
    if len(password) < 12:
        raise ValueError('Пароль ключа: не менее 12 байт.')
    private = X25519PrivateKey.generate()
    return (private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                 serialization.BestAvailableEncryption(password)),
            private.public_key().public_bytes(serialization.Encoding.PEM,
                                             serialization.PublicFormat.SubjectPublicKeyInfo))


def _public(data):
    key = serialization.load_pem_public_key(data)
    if not isinstance(key, X25519PublicKey):
        raise ValueError('Нужен публичный ключ восстановления X25519.')
    return key


def public_id(data):
    return hashlib.sha256(_public(data).public_bytes_raw()).hexdigest()


def _key(private, public, header):
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=MAGIC + header).derive(private.exchange(public))


def encrypt(source, destination, public_pem):
    public = _public(public_pem)
    ephemeral = X25519PrivateKey.generate()
    nonce = os.urandom(12)
    header = json.dumps({'version': 1, 'key_id': public_id(public_pem),
                         'ephemeral': base64.b64encode(ephemeral.public_key().public_bytes_raw()).decode(),
                         'nonce': base64.b64encode(nonce).decode()}, sort_keys=True).encode('ascii')
    prefix = MAGIC + struct.pack('!I', len(header)) + header
    cipher = Cipher(algorithms.AES(_key(ephemeral, public, header)), modes.GCM(nonce)).encryptor()
    cipher.authenticate_additional_data(prefix)
    destination.write(prefix)
    while block := source.read(BLOCK):
        destination.write(cipher.update(block))
    destination.write(cipher.finalize())
    destination.write(cipher.tag)


def decrypt(source, destination, private_pem, password):
    try:
        private = serialization.load_pem_private_key(private_pem, password=password)
        if not isinstance(private, X25519PrivateKey) or source.read(len(MAGIC)) != MAGIC:
            raise ValueError
        length = struct.unpack('!I', source.read(4))[0]
        if not 1 <= length <= 4096:
            raise ValueError
        header = source.read(length)
        data = json.loads(header)
        if set(data) != {'version', 'key_id', 'ephemeral', 'nonce'} or data['version'] != 1:
            raise ValueError
        if hashlib.sha256(private.public_key().public_bytes_raw()).hexdigest() != data['key_id']:
            raise ValueError
        ephemeral = X25519PublicKey.from_public_bytes(base64.b64decode(data['ephemeral'], validate=True))
        nonce = base64.b64decode(data['nonce'], validate=True)
        if len(nonce) != 12:
            raise ValueError
        cipher = Cipher(algorithms.AES(_key(private, ephemeral, header)), modes.GCM(nonce)).decryptor()
        cipher.authenticate_additional_data(MAGIC + struct.pack('!I', length) + header)
        # Не отдаём plaintext до проверки полного 128-битного тега.
        with tempfile.TemporaryFile() as verified:
            tail = b''
            while block := source.read(BLOCK):
                buffer = tail + block
                if len(buffer) > 16:
                    verified.write(cipher.update(buffer[:-16]))
                tail = buffer[-16:]
            if len(tail) != 16:
                raise ValueError
            verified.write(cipher.finalize_with_tag(tail))
            verified.seek(0)
            while block := verified.read(BLOCK):
                destination.write(block)
        return data
    except (InvalidTag, ValueError, TypeError, KeyError, struct.error, UnicodeError):
        raise ValueError('Архив или ключ восстановления не прошёл проверку.') from None
