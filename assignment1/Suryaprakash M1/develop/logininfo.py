
import ruamel.yaml
import os

class LoginInfo(object):
    def __init__(self):
        pass

    def __call__(self, user='ruamel'):
        yaml = ruamel.yaml.YAML(typ='safe')
        with open(os.path.expanduser('~/.ssh/passwd/bitbucket.yaml')) as fp:
            data = yaml.load(fp)
        userpass = data['passwd']
        for k in userpass:
            if k.startswith(user):
                return k, userpass[k]
        raise NotImplementedError


login_info = LoginInfo()
