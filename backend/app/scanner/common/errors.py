from flask import jsonify

class AppError(Exception):
    code = 500; msg = "internal_error"
    def __init__(self, msg=None, code=None):
        super().__init__(msg or self.msg)
        self.code = code or self.code

class BadRequest(AppError): code = 400; msg = "bad_request"
class NotFound(AppError):  code = 404; msg = "not_found"
class SFTPError(AppError): code = 422; msg = "sftp_error"

def to_http(e):
    if not isinstance(e, AppError):
        e = AppError(str(e))
    return jsonify({"error": type(e).__name__, "message": str(e)}), e.code
