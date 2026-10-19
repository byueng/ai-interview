"""业务层可安全展示的错误；HTTP 状态映射由应用层负责。"""


class InterviewError(Exception):
    """服务端流程失败，原始异常通过异常链保留。"""


class SessionNotFoundError(InterviewError):
    pass


class SessionNotConfiguredError(InterviewError):
    pass


class SessionConflictError(InterviewError):
    pass


class SessionGoneError(InterviewError):
    pass


class InvalidPresetNameError(InterviewError):
    pass


class PresetNotFoundError(InterviewError):
    pass


class InvalidPresetError(InterviewError):
    """服务器保存的预设内容损坏，不属于请求体校验错误。"""


class StorageError(InterviewError):
    pass
