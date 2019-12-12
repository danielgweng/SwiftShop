from os import urandom
from hashlib import pbkdf2_hmac, sha256
from binascii import hexlify

PASS_HASH_ALGORITHM = 'sha512'
ITERATIONS = 100000

#https://www.vitoshacademy.com/hashing-passwords-in-python/

def encrypt_password(password):
    """Hash a per-user salt + password for storing."""
    salt = sha256(urandom(60)).hexdigest().encode('ascii')
    pwdhash = pbkdf2_hmac(PASS_HASH_ALGORITHM, password.encode('utf-8'), salt, ITERATIONS)
    pwdhash = hexlify(pwdhash)
    return (salt + pwdhash).decode('ascii')

def verify_password(stored_password, provided_password):
    """Verify a stored password against one provided by user"""
    salt = stored_password[:64]
    stored_password = stored_password[64:]
    pwdhash = pbkdf2_hmac(PASS_HASH_ALGORITHM, provided_password.encode('utf-8'), salt.encode('ascii'), ITERATIONS)
    pwdhash = hexlify(pwdhash).decode('ascii')
    return pwdhash == stored_password