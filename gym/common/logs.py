import logging
import logging.config

logger = logging.getLogger(__name__)


class Logs:
    def __init__(self, filename, debug=False):

        op_mode = "DEBUG" if debug else "INFO"

        logging.config.dictConfig({
                'version': 1,
                'disable_existing_loggers': False,
                'formatters': {
                    'standard': {
                        'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
                    },
                },
                'handlers': {
                    'default': {
                        'level':op_mode,
                        'class':'logging.StreamHandler',
                        "formatter": "standard",
                    },
                    "info_file_handler": {
                        "class": "logging.handlers.RotatingFileHandler",
                        "level": "DEBUG",
                        "formatter": "standard",
                        "filename": filename,
                        "maxBytes": 10485760,
                        "backupCount": 20,
                        "encoding": "utf8"
                    },
                },
                'loggers': {
                    '': {
                        'handlers': ['default', 'info_file_handler'],
                        'level': 'DEBUG',
                        'propagate': True
                    }
                }
            })
