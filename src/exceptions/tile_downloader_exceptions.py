class TileDownloaderException(Exception):
    """Base exception for tile downloader"""
    pass


class ConfigurationError(TileDownloaderException):
    """Configuration related errors"""
    pass


class DownloadError(TileDownloaderException):
    """Download related errors"""
    pass


class ServerError(TileDownloaderException):
    """Server related errors"""
    pass


class ValidationError(TileDownloaderException):
    """Validation related errors"""
    pass 