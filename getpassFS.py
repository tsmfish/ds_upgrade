import base64
import os
import re


class getpassFS(object):
    USER, PASSWORD = 'user', 'password'
    pattern = re.compile(r'\b(\S+)\s*:\s*(\S+)', re.IGNORECASE)
    authority = {}

    def __init__(self, file_name):
        if os.path.isfile(file_name):
            with open(file_name, 'r') as file:
                for line in file:
                    try:
                        key, value = self.pattern(line).search(line)
                        self.authorit[key] = value
                    except IndexError as error:
                        pass
                    except KeyError as error:
                        pass

    def getuser(self):
        if self.authority.has_key(getpassFS.USER):
            return self.authority[getpassFS.USER]
        else:
            return ""

    def getpass(self):
        if self.authority.has_key(getpassFS.PASSWORD):
            return base64.b64decode(self.authority[getpassFS.PASSWORD]).decode('ascii')
        else:
            return ""
