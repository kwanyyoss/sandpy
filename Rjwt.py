import types
import jwt

if not '__mod' in globals():
    import sys
    globals()['__mod'] = sys.modules[__name__]
    __main__ = sys.modules['__main__']
    jwt.algorithms.json = __main__.Rjson
    jwt.api_jwk.json = __main__.Rjson
    jwt.api_jws.json = __main__.Rjson
    jwt.api_jwt.json = __main__.Rjson
    jwt.jwks_client.json = __main__.Rjson


def patch(myexc_cls, mkapi):
    # from "pyjwt/jwt/exceptions.py"
    class PyJWTError(myexc_cls):
        """
        Base class for all exceptions
        """
        pass


    class InvalidTokenError(PyJWTError):
        pass


    class DecodeError(InvalidTokenError):
        pass


    class InvalidSignatureError(DecodeError):
        pass


    class ExpiredSignatureError(InvalidTokenError):
        pass


    class InvalidAudienceError(InvalidTokenError):
        pass


    class InvalidIssuerError(InvalidTokenError):
        pass


    class InvalidIssuedAtError(InvalidTokenError):
        pass


    class ImmatureSignatureError(InvalidTokenError):
        pass


    class InvalidKeyError(PyJWTError):
        pass


    class InvalidAlgorithmError(InvalidTokenError):
        pass


    class MissingRequiredClaimError(InvalidTokenError):
        def __init__(self, claim):
            self.claim = claim

        def __str__(self):
            return 'Token is missing the "%s" claim' % self.claim


    class PyJWKError(PyJWTError):
        pass


    class PyJWKSetError(PyJWTError):
        pass


    class PyJWKClientError(PyJWTError):
        pass

    exceptions = types.SimpleNamespace()
    exceptions.PyJWTError = PyJWTError
    exceptions.InvalidTokenError = InvalidTokenError
    exceptions.DecodeError = DecodeError
    exceptions.InvalidSignatureError = InvalidSignatureError
    exceptions.ExpiredSignatureError = ExpiredSignatureError
    exceptions.InvalidAudienceError = InvalidAudienceError
    exceptions.InvalidIssuerError = InvalidIssuerError
    exceptions.InvalidIssuedAtError = InvalidIssuedAtError
    exceptions.ImmatureSignatureError = ImmatureSignatureError
    exceptions.InvalidKeyError = InvalidKeyError
    exceptions.InvalidAlgorithmError = InvalidAlgorithmError
    exceptions.MissingRequiredClaimError = MissingRequiredClaimError
    exceptions.PyJWKError = PyJWKError
    exceptions.PyJWKSetError = PyJWKSetError
    exceptions.PyJWKClientError = PyJWKClientError

    __mod.exceptions = exceptions
    __mod.__dict__.update(exceptions.__dict__)
    for i in exceptions.__dict__.values():
        i.lock()
    del i
    del exceptions

    def map_exceptions(func):
        map = { jwt.exceptions.PyJWTError: PyJWTError,
                jwt.exceptions.InvalidTokenError: InvalidTokenError,
                jwt.exceptions.DecodeError: DecodeError,
                jwt.exceptions.InvalidSignatureError: InvalidSignatureError,
                jwt.exceptions.ExpiredSignatureError: ExpiredSignatureError,
                jwt.exceptions.InvalidAudienceError: InvalidAudienceError,
                jwt.exceptions.InvalidIssuerError: InvalidIssuerError,
                jwt.exceptions.InvalidIssuedAtError: InvalidIssuedAtError,
                jwt.exceptions.ImmatureSignatureError: ImmatureSignatureError,
                jwt.exceptions.InvalidKeyError: InvalidKeyError,
                jwt.exceptions.InvalidAlgorithmError: InvalidAlgorithmError,
              }

        if jwt.__version__ >= '2.':
            map[jwt.exceptions.PyJWKError] = PyJWKError
            map[jwt.exceptions.PyJWKSetError] = PyJWKSetError
            map[jwt.exceptions.PyJWKClientError] = PyJWKClientError

        def wrapped(*argv, **kwargs):
            try:
                return func(*argv, **kwargs)
            except jwt.exceptions.PyJWTError as e:
                if type(e) == jwt.exceptions.MissingRequiredClaimError:
                    raise MissingRequiredClaimError(e.claim)
                raise map[type(e)](str(e))
        return wrapped

    __mod.encode = mkapi("""
def fn(payload, key, algorithm="HS256", headers=None, json_encoder=None):
  return f(payload, key, algorithm, headers, json_encoder)
""",                     f=map_exceptions(jwt.encode))

    __mod.decode = mkapi("""
def fn(token, key="", algorithms=None, options=None, **kwargs):
  return f(token, key, algorithms, options, **kwargs)
""",                     f=map_exceptions(jwt.decode))

    __mod.__all__ = [ 'exceptions',
                      'PyJWTError', 'InvalidTokenError', 'DecodeError',
                      'InvalidSignatureError', 'ExpiredSignatureError',
                      'InvalidAudienceError', 'InvalidIssuerError',
                      'InvalidIssuedAtError', 'ImmatureSignatureError',
                      'InvalidKeyError', 'InvalidAlgorithmError',
                      'MissingRequiredClaimError', 'PyJWKError', 'PyJWKSetError',
                      'PyJWKClientError', 'encode', 'decode' ]
    del __mod.patch

__mod.patch = patch

