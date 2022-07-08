class SignedClass(metaclass=hidebases(()).__base__):
    public_key = None
    def __init_subclass__(cls, *, private_key, **kwargs):
        super().__init_subclass__(**kwargs)
        if isinstance(private_key, bytes) or\
           isinstance(private_key, str):
            signature = { 'id': id(cls) }
            cls.__verifier__ = pyjwt.encode(signature, private_key,
                                            algorithm='RS256')
        ########
        # If one wants a class to be a globally known and identifiable
        # interface, it should probably not be monkey-patched once it is
        # defined.
        freeze_meta = hidebases(()).__base__
        freeze_meta.lock(cls)
    @classmethod
    def verify(cls, foreign):
        """
        Given another class, checks whether it is the same as this class.  If so,
        the calling module is expected to forget (e.g. delete) this class, and use
        the evaluated class in its place.  This faciliates reuse and`evaluations
        of class hierarchies with code loaded prior to the calling module.
        """
        if istype(foreign) and\
           isinstance(getattr(foreign, '__verifier__', None), str):
            # JWT
            try:
                signature = pyjwt.decode(foreign.__verifier__, cls.public_key,
                                         algorithms=['RS256'])
            except pyjwt.exceptions.InvalidTokenError:
                return False
            if isinstance(signature, dict) and 'id' in signature:
                return signature['id'] == id(foreign)
        return False
    @classmethod
    def __dir__(cls):
        return object.__dir__(cls)
SignedClass.lock()

# ---------
# EXAMPLE
# ---------

class Test(Object,
           SignedClass, private_key=b"""-----BEGIN RSA PRIVATE KEY-----
MIICXgIBAAKBgQDfa5hxnxzMnFAxQTwgg+lKP5zk8PxfE5bvmwzsOmE1Xcd9WNgg
f1xPfUuG6F/hlKXzWyUcTRlZsx6nRO5Tm8V3wMfMJLBxYDW2AbXoRtCGhBQD0xzl
hIyrc87X5ZykT1c76tAeJRfJqxNjhXZeE/8tW920bYrdoukcZGa5M+LkzwIDAQAB
AoGAJ0lAMRqNcd06rK6P6BfJ+ehdqlRFzGIhdFiLWS6a0UuAPKZWusAqdz/M/Bf4
ZC5DUBuC1wsnngJFLZyNW95URnpO5MXlZpMzOK5J95JPry3lgXEnrEA7hFNa7Vzc
aD/6igDGkJWQKBN/ssBvVY7CxkeleJhGx1LFmq3yGskGX6ECQQD46/2lsp8AyldR
JJXO3uRVtopQkwQA3xDi3ZNy+eix6xc2nsJSA4J/ISVJkRtW2qNGD+BgC5Nh1288
yHU9T7FVAkEA5cX3zCksjN/0SwhwfxGtm9Kxbm6R/RA5SqwesBYLwZ1TotpWIoB4
ftsXC2vs2v3c75nAjdJ4VkkXcGAjMaPNkwJBAMoXFjPrY6nJnMBU+occcLah34Nx
CEQI1fXJvIcRG/kuiwceN1dMYCsEZvhmJZMLKJmeFCUF4N8Df90SRhTD2Y0CQQCH
QiFbwoUiLJePL9mhQ5PSHZYrLtWrhchkB6xM9b1X7TgVrrdzufK0ol4PcCnOxBAx
z22FTvddu8sbcMxm5UkXAkEAxXI3IRNX9kYIJLFG8z7xBIAhC2zrAoFmIm0+LqD5
AllciW+YUoZPAj1/f98p/+V5oUkETUfk4p+SNEseXWLoNQ==
-----END RSA PRIVATE KEY-----"""):
    public_key=b"""-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDfa5hxnxzMnFAxQTwgg+lKP5zk
8PxfE5bvmwzsOmE1Xcd9WNggf1xPfUuG6F/hlKXzWyUcTRlZsx6nRO5Tm8V3wMfM
JLBxYDW2AbXoRtCGhBQD0xzlhIyrc87X5ZykT1c76tAeJRfJqxNjhXZeE/8tW920
bYrdoukcZGa5M+LkzwIDAQAB
-----END PUBLIC KEY-----"""
__mod.example = Test

