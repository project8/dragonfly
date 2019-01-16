import logging


log = logging.getLogger("hornet")
    
def initializeLogging():
    log.setLevel(logging.INFO)
        
def configureLogging(config):
    if 'logger' in config  and 'level' in config['logger']:
        level = config['logger']['level']
        try:
            level = logging.getLevelName(level)
            log.setLevel(level)
        except ValueError, err:
            log.warning(" Invalid logging-level configuration value: " + level)
