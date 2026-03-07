import os
import json
import time
import uuid
import pytz
import logging as log
from datetime import datetime
from app.config.config import settings
from app.libraries.RabbitMQ import push_to_rabbitmq

NOTICE_LEVEL = 25
log.addLevelName(NOTICE_LEVEL, 'NOTICE')

class Logger:
    _instance = None  # Class-level variable to hold the single instance
    # Set this to False for disable logging for [log_debug, log_info, log_waring, log_notice]
    log_flag = getattr(settings, 'LOGGING', True)
    log_path = getattr(settings, 'LOG_FILE_PATH', 'logs')
    retention_days = getattr(settings, 'LOG_RETENTION_DAYS', '7')
    elk_logging = getattr(settings, 'ELK_LOGGING', False)
    app_timezone = getattr(settings, 'APP_TIMEZONE', False)
    
    def __init__(self):
        """
        Initializes the Logger class to manage logging setup.

        Args:
            logger_name (str): The name of the logger.
            log_file_name (str): The name of the file to log messages to.
        """
        self.logger_name=settings.LOG_LABEL        
        self.log_file_name=settings.LOG_FILE_PREFIX
        
        # Prevent further instantiation
        if Logger._instance is not None:
            raise RuntimeError("This class is a singleton! Use get_instance() to retrieve it.")
        
        self.endpoint = None
        # Generate log file path based on current date
        self.timezone = pytz.timezone(self.app_timezone)
        current_date = datetime.now(self.timezone).strftime('%Y-%m-%d')
        log_file_name = f"{self.log_file_name}_{current_date}.log"
        # Define the full log file path
        logging_file = os.path.join(self.log_path, log_file_name)
        os.makedirs(self.log_path, exist_ok=True)
        
        # Check if the log file exists; if not, create it
        if not os.path.exists(logging_file):
                open(logging_file, 'w').close()

        # Use the log file path
        self.log_file_path = logging_file
        
        self._daily_log_file()
        self._apply_retention_policy()  # Apply the retention policy on initialization
        
        # Initialize logger
        self.logger_instance = log.getLogger(self.logger_name)
        self.logger_instance.setLevel(log.DEBUG)
        
        # Initialize UUID and LoggerAdapter
        self.uuid = None
        self.logger_instance.addFilter(self._add_uuid_to_record)  # Add custom filter to inject UUID
        
        # Formatter for logs (including the level name and UUID)
        log_format = log.Formatter("[%(asctime)s] - %(levelname)s - [%(uuid)s] - %(message)s", datefmt="%d/%m/%Y %I:%M:%S %p")
        
        # File handler (append mode)
        logs_to_file = log.FileHandler(self.log_file_path, mode="a", encoding="utf-8")
        logs_to_file.setLevel(log.DEBUG)
        logs_to_file.setFormatter(log_format)
        # Add handlers to the logger
        self.logger_instance.addHandler(logs_to_file)
    
    @staticmethod
    def get_instance(set_uuid=False):
        """
        Returns the singleton instance of Logger.
        If not already created, it initializes the instance.

        Args:
            logger_name (str): Name of the logger.
            log_file_name (str): Log file base name.

        Returns:
            Logger: The singleton Logger instance.
        """
        if Logger._instance is None:
            Logger._instance = Logger()
        if set_uuid:
            Logger._instance.__set_uuid()
        return Logger._instance
    
    def set_endpoint(self, endpoint):
        """Set the endpoint for the current log instance."""
        self.endpoint = endpoint
    
    def __set_uuid(self):
        """Generates and sets a new UUID for the current log group."""
        self.uuid = str(uuid.uuid4())
    
    def _add_uuid_to_record(self, record):
        """Injects the UUID into the log record, so each log message has a UUID field."""
        record.uuid = self.uuid if self.uuid else "N/A"
        record.endpoint = self.endpoint if self.endpoint else "[-]"
        return True
    
    def _daily_log_file(self):
        """Ensures the daily log file exists, creating it if necessary."""
        if not os.path.isfile(self.log_file_path):
            os.makedirs(os.path.dirname(self.log_file_path), exist_ok=True)
            with open(self.log_file_path, 'a'):
                pass  # Just to create the file if it doesn't exist
    
    def _apply_retention_policy(self):
        """Apply retention policy: Delete logs older than retention_days."""
        current_time = time.time()
        
        # Walk through the log directory and check file ages
        for root, dirs, files in os.walk(self.log_path):
            for file in files:
                file_path = os.path.join(root, file)
                if file.endswith('.log'):  # You can add other log file extensions if needed
                    file_age = current_time - os.path.getmtime(file_path)
                    if file_age > int(self.retention_days) * 86400:  # 86400 seconds in a day
                        os.remove(file_path)
                        print(f"Deleted old log file: {file_path}")
    
    def _format_message(self, message, elk_flag=False, log_level=None):
        """Formats the message to a single-line JSON if it's a dictionary."""
        if isinstance(message, dict):
            if elk_flag:
                # Construct the RMQ message with additional fields
                rmq_message = {
                    'log_data': message,
                    'log_ts': datetime.now(self.timezone).strftime("%d/%m/%Y %I:%M:%S %p"),
                    'request_id': self.uuid if hasattr(self, 'uuid') and self.uuid else "",
                    'log_type': log_level if log_level else "N/A",
                }
                return json.dumps(rmq_message, separators=(',', ':'))  # Single-line JSON
            # Default JSON formatting for dictionaries
            return json.dumps(message, separators=(',', ':'))  # Single-line JSON
        return message  # Return the message as-is if not a dictionary
    
    def log_debug(self, message):
        if self.log_flag:
            log_message = self._format_message(message, self.elk_logging, log_level="DEBUG")
            if self.elk_logging:
                push_to_rabbitmq(log_message)
            else:
                self.logger_instance.debug(log_message)
        
    def log_error(self, message):
        log_message = self._format_message(message, self.elk_logging, log_level="ERROR")
        if self.elk_logging:
            push_to_rabbitmq(log_message)
        else:
            self.logger_instance.error(log_message)
        
    def log_info(self, message):
        if self.log_flag:
            log_message = self._format_message(message, self.elk_logging, log_level="INFO")
            if self.elk_logging:
                push_to_rabbitmq(log_message)
            else:
                self.logger_instance.info(log_message)
        
    def log_warning(self, message):
        if self.log_flag:
            log_message = self._format_message(message, self.elk_logging, log_level="WARNING")
            if self.elk_logging:
                push_to_rabbitmq(log_message)
            else:
                self.logger_instance.warning(log_message)
        
    def log_critical(self, message):
        log_message = self._format_message(message, self.elk_logging, log_level="CRITICAL")
        if self.elk_logging:
            push_to_rabbitmq(log_message)
        else:
            self.logger_instance.critical(log_message)

    # Step 2: Create a method for the custom level (NOTICE)
    def log_notice(self, message):
        if self.log_flag:
            log_message = self._format_message(message, self.elk_logging, log_level="NOTICE")
            if self.elk_logging:
                push_to_rabbitmq(log_message)
            else:
                self.logger_instance.log(NOTICE_LEVEL, log_message)
