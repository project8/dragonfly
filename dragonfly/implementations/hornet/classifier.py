import hornet
import re, os

class TypeInfo():
    def __init__(self):
        self.name = ''
        self.doMatchExtension = False
        self.extension = ''
        self.doMarchRegexp = False
        self.regexpTemplate = r''
        self.doHash = False
        self.jobs = []

class JobInfo():
    def __init__(self):
        self.name = ''
        self.fileType = ''
        self.command = ''
        self.commandTemplate = '' # not sure what it is...will change later
    
    
def validateClassifierConfig(config_classifier):
    types = []
    try:
        types = config_classifier['types']
    except KeyError:
        hornet.log.critical(' No types were provided.')
        return
    for t in types:
        tests = 0
        if 'name' not in t or t['name'] == '':
            hornet.log.critical(' Type ' + str(t) + ' is missing its name.')
        if 'match-extension' in t and t['match-extension'] != '':
            tests += 1
        if 'match-regexp' in t and t['match-regexp'] != '':
            regexp = t['match-regexp']
            try:
                re.compile(regexp)
                tests += 1
            except re.error:
                hornet.log.critical(' Invalid regular expression: ' + regexp)
        if tests == 0:
            hornet.log.critical(' No tests were provided for type ' +str(t))
    if 'base-paths' in config_classifier:
        paths = config_classifier['base-paths']
        home = os.path.expanduser('~')
        for p in paths:
            absolutePath = os.path.join(home, p)
            if not os.path.isdir(absolutePath):
                hornet.log.critical(' Invalid base path: ' + absolutePath)

def getSubPath(basePaths, absolutePath):
    subPath = ""
    for basepath in basePaths:
        if path.startswith(basePath):
            try:
                subpath = os.path.relpath(path, basePath)
                break
            except Exception: # ?
                hornet.log.warning(' Unable to get the relative path of ' + path + ' after checking prefix ' + basePath)
    return subPath


def Classifier():
# trying to learn Go context...
