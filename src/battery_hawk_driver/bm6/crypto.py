"""BM6 AES encryption utilities."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cryptography.hazmat.primitives.ciphers import Cipher

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .constants import BM6_AES_BLOCK_SIZE, BM6_AES_KEY


class BM6Crypto:
    """AES encryption/decryption for BM6 protocol."""

    def __init__(self, logger: logging.Logger | None = None) -> None:
        """Initialize BM6 crypto with AES key."""
        self.logger = logger or logging.getLogger(__name__)
        self.key = BM6_AES_KEY

    def encrypt(self, data: bytes) -> bytes:
        """
        Encrypt data using AES-ECB mode (no IV), as required by BM6 protocol.

        Args:
            data: Data to encrypt (must be exactly 16 bytes for BM6 protocol)

        Returns:
            Encrypted data
        """
        try:
            # BM6 protocol expects exactly 16 bytes - no padding needed
            if len(data) != BM6_AES_BLOCK_SIZE:
                self.logger.warning(
                    "BM6 data should be exactly %d bytes, got %d bytes. Padding/truncating.",
                    BM6_AES_BLOCK_SIZE,
                    len(data),
                )
                if len(data) < BM6_AES_BLOCK_SIZE:
                    # Pad with zeros to 16 bytes
                    data = data + b"\x00" * (BM6_AES_BLOCK_SIZE - len(data))
                else:
                    # Truncate to 16 bytes
                    data = data[:BM6_AES_BLOCK_SIZE]

            # IMPORTANT: BM6 protocol requires AES-ECB (no IV). Do NOT change to CBC/CTR/etc.
            # Devices will silently ignore commands if the mode is incorrect.
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.ECB(),  # noqa: S305  # nosec B305 - BM6 protocol requires ECB (device protocol)
                backend=default_backend(),
            )
            encryptor = cipher.encryptor()

            # Encrypt the data (no padding needed since data is exactly 16 bytes)
            encrypted = encryptor.update(data) + encryptor.finalize()

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
        Decrypt data using AES-ECB mode (no IV), as required by BM6 protocol.

        Args:
            data: Data to decrypt (should be 16 bytes for BM6 protocol)

        Returns:
            Decrypted data
        """
        try:
            # BM6 protocol uses 16-byte blocks
            if len(data) != BM6_AES_BLOCK_SIZE:
                self.logger.warning(
                    "BM6 encrypted data should be exactly %d bytes, got %d bytes",
                    BM6_AES_BLOCK_SIZE,
                    len(data),
                )

            # IMPORTANT: BM6 protocol requires AES-ECB (no IV). Do NOT change to CBC/CTR/etc.
            # Devices will silently ignore responses if the mode is incorrect.
            cipher = Cipher(
                algorithms.AES(self.key),
                modes.ECB(),  # noqa: S305  # nosec B305 - BM6 protocol requires ECB (device protocol)
                backend=default_backend(),
            )
            decryptor = cipher.decryptor()

            # Decrypt the data
            decrypted = decryptor.update(data) + decryptor.finalize()

            # BM6 protocol uses exactly 16-byte blocks - don't strip any bytes
            # as null bytes may be part of the actual command/data

            self.logger.debug(
                "Decrypted %d bytes to %d bytes",
                len(data),
                len(decrypted),
            )

        except Exception:
            self.logger.exception("Failed to decrypt data.")
            return data

        return decrypted

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
