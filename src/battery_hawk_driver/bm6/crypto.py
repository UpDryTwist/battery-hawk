"""BM6 AES encryption utilities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.ciphers import Cipher

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .constants import BM6_AES_KEY


class BM6Crypto:
    """AES encryption/decryption for BM6 protocol."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize BM6 crypto with AES key."""
        self.logger = logger or logging.getLogger(__name__)
        self.key = BM6_AES_KEY

    def encrypt(self, data: bytes) -> bytes:
        """
        Encrypt data using AES-ECB mode.

        Args:
            data: Data to encrypt

        Returns:
            Encrypted data
        """
        try:
            # Pad data to 16-byte blocks
            padded_data = self._pad_data(data)

            # Create AES cipher in ECB mode
            # nosec B305 - ECB mode is required by BM6 device protocol
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.ECB(),  # nosec B305  # noqa: S305
                backend=default_backend(),
            )
            encryptor = cipher.encryptor()

            # Encrypt the data
            encrypted = encryptor.update(padded_data) + encryptor.finalize()

            self.logger.debug(
                "Encrypted %d bytes to %d bytes",
                len(data),
                len(encrypted),
            )
        except Exception:
            self.logger.exception("Failed to encrypt data.")
            return data

        return encrypted

    def decrypt(self, data: bytes) -> bytes:
        """
        Decrypt data using AES-ECB mode.

        Args:
            data: Data to decrypt

        Returns:
            Decrypted data
        """
        try:
            # Create AES cipher in ECB mode
            # nosec B305 - ECB mode is required by BM6 device protocol
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.ECB(),  # nosec B305  # noqa: S305
                backend=default_backend(),
            )
            decryptor = cipher.decryptor()

            # Decrypt the data
            decrypted = decryptor.update(data) + decryptor.finalize()

            # Remove padding
            unpadded = self._unpad_data(decrypted)

            self.logger.debug(
                "Decrypted %d bytes to %d bytes",
                len(data),
                len(unpadded),
            )

        except Exception:
            self.logger.exception("Failed to decrypt data.")
            return data

        return unpadded

    def _pad_data(self, data: bytes) -> bytes:
        """
        Pad data to 16-byte blocks using PKCS7 padding.

        Args:
            data: Data to pad

        Returns:
            Padded data
        """
        block_size = 16
        padding_length = block_size - (len(data) % block_size)
        padding = bytes([padding_length] * padding_length)
        return data + padding

    def _unpad_data(self, data: bytes) -> bytes:
        """
        Remove PKCS7 padding from data.

        Args:
            data: Padded data

        Returns:
            Unpadded data
        """
        if not data:
            return data

        padding_length = data[-1]
        if padding_length > 16 or padding_length == 0:  # noqa: PLR2004
            # Invalid padding, return original data
            return data

        # Verify padding
        padding = data[-padding_length:]
        if not all(b == padding_length for b in padding):
            # Invalid padding, return original data
            return data

        return data[:-padding_length]
