'''
Copyright 2017 John Torakis
Copyright 2021 Edwin Kwan
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
 http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

Copied and adapted from "httpimport" project (GitHub) (labled below),
for sandboxing requirements
'''

import types
import logging
import io
import zipfile
import tarfile
import os

from contextlib import contextmanager
from urllib import request, parse
import re

from bases import ReadOnly_meta

__author__ = 'John Torakis - operatorequals'
__version__ = '0.8.0'
__github__ = 'https://github.com/operatorequals/httpimport'


'''
To enable debug logging set:
>>> import logging; logging.getLogger('httpimport').setLevel(logging.DEBUG)
in your script.
'''

log_level = logging.WARN
log_format = '%(message)s'

logger = logging.getLogger(__name__)
logger.setLevel(log_level)
log_handler = logging.StreamHandler()
log_handler.setLevel(log_level)
log_formatter = logging.Formatter(log_format)
log_handler.setFormatter(log_formatter)
logger.addHandler(log_handler)


class HttpImporter(object):
    """
The 'modules' parameter is a list, with the names of the modules/packages that can be imported from the given URL.
The 'base_url' parameter is a string containing the URL where the repository/directory is served through HTTP/S
It is better to not use this class directly, but through its wrappers ('remote_repo', 'github_repo', etc).
    """

    TAR_ARCHIVE = 'tar'
    ZIP_ARCHIVE = 'zip'
    WEB_ARCHIVE = 'html'
    ARCHIVE_TYPES = [
        ZIP_ARCHIVE,
        TAR_ARCHIVE,
        WEB_ARCHIVE
    ]

    def __init__(self, g, cauterer, modules, base_url, zip_pwd=None):
        self.globals = g
        self.cauterer = cauterer
        self.module_names = modules
        self.base_url = base_url.strip()
        if parse.urlparse(self.base_url).netloc and self.base_url[-1] != '/':
            self.base_url += '/'
        self.in_progress = {}
        self.__zip_pwd = zip_pwd

        try:
            self.filetype, self.archive = _detect_filetype(base_url)
            logger.info("[+] Filetype detected '%s' for '%s'" % (self.filetype, self.base_url))
        except IOError:
            raise ImportError("URL content cannot be detected or opened (%s)" % self.base_url)

        self.is_archive = False
        if self.filetype in [HttpImporter.TAR_ARCHIVE, HttpImporter.ZIP_ARCHIVE]:
            self.is_archive = True

        if self.is_archive:
            logger.info("[+] Archive file loaded successfully from '%s'!" % self.base_url)
            self._paths = _list_archive(self.archive)


    def _mod_to_filepaths(self, fullname):
        suffix = '.py'
        # get the python module name
        py_filename = fullname.replace(".", os.sep) + suffix
        # get the filename if it is a package/subpackage
        py_package = fullname.replace(".", os.sep, fullname.count(".") - 1) + "/__init__" + suffix

        if self.is_archive:
            return {'module': py_filename, 'package': py_package, 'raw': fullname}
        else:
            # if self.in_progress:
            # py_package = fullname.replace(".", '/') + "/__init__" + suffix
            return {
            'module': self.base_url + py_filename,
            'package': self.base_url + py_package
            }


    def _mod_in_archive(self, fullname):
        paths = self._mod_to_filepaths(fullname)
        return set(self._paths) & set(paths.values())


    def find_module(self, fullname):
        fullname = fullname.strip()
        logger.debug("FINDER=================")
        logger.debug("[!] Searching %s" % fullname)
        logger.info("[@] Checking if in declared remote module names >")
        if fullname.split('.')[0] not in self.module_names:
            logger.info("[-] Not found!")
            return None

        if fullname in self.in_progress:
            return None

        self.in_progress[fullname] = True

        if self.is_archive:
            logger.info("[@] Checking if module exists in loaded Archive file >")
            if self._mod_in_archive(fullname) is None:
                logger.info("[-] Not Found in Archive file!")
                return None

        logger.info("[*] Module/Package '%s' can be loaded!" % fullname)
        del(self.in_progress[fullname])
        return self


    def load_module(self, name, imports={}, data=None, timeout=0):
        name = name.strip()
        if not timeout:
            timeout = 0
        elif type(timeout) != int:
            raise TypeError("'timeout' must be an integer in seconds")
          
        logger.debug("LOADER=================")
        logger.debug("[+] Loading %s" % name)

        try:
            if name.startswith('.') or\
               name.find('..') >= 0 or name.find(os.sep + os.sep) >= 0 or\
               (not parse.urlparse(self.base_url).netloc and\
                name.startswith(os.sep)):
                raise ValueError("illegal module name")
            mod_dict = self._open_module_src(name, data, timeout)
            module_src = mod_dict['source']
            filepath = mod_dict['path']
            module_type = mod_dict['type']

        except ValueError:
            module_src = None
            logger.info("[-] '%s' is not a module:" % name)
            logger.warning("[!] '%s' not found in location" % name)
            return None

        logger.debug("[+] Importing '%s'" % name)

        class module(types.ModuleType, metaclass=ReadOnly_meta):
            __repr__ = types.ModuleType.__repr__
            def __init__(self, *argv, **kwargs):
                super().__init__(*argv, **kwargs)
            def __setattr__(self2, key, val):
                if isinstance(val, types.FunctionType):
                    val = self.globals['fn'](val)
                return super().__setattr__(key, val)
        mod = module(name)

        mkapi = self.globals['makeapi']
        mod.__loader__ = mkapi("fn = lambda _=None: f",
                               f=mkapi("__loader__ = lambda name: f(name)",
                                       __fname__='__loader__',
                                       f=self.load_module.__get__(self))._c)
        del mkapi

        # remove double slashes
        schemeinit = parse.urlparse(filepath).scheme
        if filepath.startswith(schemeinit + '://'):
            schemeinit += ':/'
            filepath = schemeinit + re.sub(r'//+', '/',
                                           filepath[len(schemeinit):])
        else:
            filepath = re.sub(r'//+', '/', filepath)
        del schemeinit
        mod.__file__ = filepath
        if module_type == 'package':
            mod.__package__ = name
        else:
            mod.__package__ = name.split('.')[0]

        try:
            mod.__path__ = ['/'.join(mod.__file__.split('/')[:-1]) + '/']
        except:
            mod.__path__ = self.base_url
        # clone globals
        g = self.globals.copy()
        g['__builtins__'] = g['__builtins__'].copy()
        g.update(mod.__dict__)
        self.cauterer(g)
        
        g['__mod'] = mod
        g.lock()

        if module_type == 'raw':
            logger.debug("[+] Load binary file '%s'" % name)
            mod = module_src.read()	# gets the entire file
        else:
            logger.debug("[+] Ready to execute '%s' code" % name)
            self.globals['__builtins__']['exec'](module_src.decode('utf-8'), g,
                                                 imports.copy())
        logger.info("[+] '%s' imported succesfully!" % name)
        return mod

    def _open_module_src(self, fullname, data, timeout):
        paths = self._mod_to_filepaths(fullname)
        mod_type = 'module'
        if self.is_archive:
            try:
                correct_filepath_set = set(self._paths) & set(paths.values())
                filepath = correct_filepath_set.pop()
            except KeyError:
                raise ImportError("Module '%s' not found in archive" % fullname)

            content = _open_archive_file(self.archive, filepath, 'r', zip_pwd=self.__zip_pwd).read()
            src = content
            logger.info('[+] Source from archived file "%s" loaded!' % filepath)
            if paths['raw'] == filepath:
                mod_type = 'raw'
        else:
            content = None
            for mod_type in paths.keys():
                filepath = paths[mod_type]
                try:
                    logger.debug("[*] Trying '%s' for module/package %s" % (filepath,fullname))
                    if timeout:
                        content = request.urlopen(filepath, data, timeout).read()
                    else:
                        content = request.urlopen(filepath, data).read()
                    break
                except IOError:
                    logger.info("[-] '%s' is not a %s" % (fullname,mod_type))

            if content is None:
                raise ValueError("Module '%s' not found in URL '%s'" % (fullname,self.base_url))

            src = content
            logger.info("[+] Source loaded from URL '%s'!'" % filepath)

        return {
            'source': src,
            'path': filepath,
            'type': mod_type
        }
# class HttpImporter --}

def _open_archive_file(archive_obj, filepath, mode='r', zip_pwd=None):
    if isinstance(archive_obj, tarfile.TarFile):
        return archive_obj.extractfile(filepath)
    if isinstance(archive_obj, zipfile.ZipFile):
        return archive_obj.open(filepath, mode, pwd=zip_pwd)

    raise ValueError("Object is not a ZIP or TAR archive")

def _list_archive(archive_obj):
    if isinstance(archive_obj, tarfile.TarFile):
        return archive_obj.getnames()
    if isinstance(archive_obj, zipfile.ZipFile):
        return [x.filename for x in archive_obj.filelist]

    raise ValueError("Object is not a ZIP or TAR archive")

def _detect_filetype(base_url):
    try:
        resp_obj = request.urlopen(base_url)
        resp = resp_obj.read()
        if "text" in resp_obj.headers['Content-Type']:
            logger.info("[+] Response of '%s' is HTML. - Content-Type: %s" % (base_url, resp_obj.headers['Content-Type']))
            return HttpImporter.WEB_ARCHIVE, resp

    except Exception as e:   # Base URL is not callable in GitHub /raw/ contents - returns 400 Error
        logger.info("[!] Response of '%s' triggered '%s'" % (base_url, e))
        return HttpImporter.WEB_ARCHIVE, None

    resp_io = io.BytesIO(resp)
    try:
        tar = tarfile.open(fileobj=resp_io, mode='r:*')
        logger.info("[+] Response of '%s' is a Tarball" % base_url)
        return HttpImporter.TAR_ARCHIVE, tar
    except tarfile.ReadError:
        logger.info("Response of '%s' is not a (compressed) tarball" % base_url)

    try:
        zip = zipfile.ZipFile(resp_io)
        logger.info("[+] Response of '%s' is a ZIP file" % base_url)
        return HttpImporter.ZIP_ARCHIVE, zip
    except zipfile.BadZipfile:
        logger.info("Response of '%s' is not a ZIP file" % base_url)

    raise IOError("Content of URL '%s' is Invalid" % base_url)


class Importer:
    def __init__(self, g, cauterer):
        self.globals = g
        self.cauterer = cauterer
        self.searchstack = []

    def get_loader(self, fullname):
        for importer in self.searchstack:
            res = importer.find_module(fullname)
            if res:
                return self.globals['makeapi']("""
def __loader__(name, imports={}, data=None, timeout=0):
  return f(name, imports, data, timeout)
""",                                           __fname__='__loader__',
                                               f=res.load_module.__get__(res))._c
        return None

    def add_remote_repo(self, names, base_url, zip_pwd=None):
        importer = HttpImporter(self.globals, self.cauterer, names, base_url,
                                zip_pwd)
        self.searchstack.insert(0, importer)
        return importer
    def remove_remote_repo(self, importer):
        self.searchstack.remove(importer)
    @contextmanager
    def remote_repo(self, modules, base_url, zip_pwd=None):
        '''
    Context Manager that provides remote import functionality through a URL.
    The parameters are the same as the HttpImporter class contructor.
        '''
        importer = self.add_remote_repo(modules, base_url, zip_pwd=zip_pwd)
        try:
            yield self
        except ImportError as e:
            raise e
        finally:    # Always remove the added HttpImporter
            self.remove_remote_repo(importer)

    def _add_git_repo(self, url_builder, username=None, repo=None, module=None,
                      branch=None, commit=None, **kw):
        '''
    Function that creates and adds to the 'sys.meta_path' an HttpImporter object equipped with a URL of a Online Git server.
    The 'url_builder' parameter is a function that accepts the username, repo and branch/commit, and creates a HTTP/S URL of a Git server. Compatible functions are '__create_github_url', '__create_bitbucket_url'.
    The 'username' parameter defines the Github username which is the repository's owner.
    The 'repo' parameter defines the name of the repo that contains the modules/packages to be imported.
    The 'module' parameter is optional and is a list containing the modules/packages that are available in the chosen Github repository.
    If it is not provided, it defaults to the repositories name, as it is common that the a Python repository at "github.com/someuser/somereponame" contains a module/package of "somereponame".
    The 'branch' and 'commit' parameters cannot be both populated at the same call. They specify the branch (last commit) or specific commit, that should be served.
        '''
        if username == None or repo == None:
            raise Error("'username' and 'repo' parameters cannot be None")
        if commit and branch:
            raise Error("'branch' and 'commit' parameters cannot be both set!")

        if commit:
            branch = commit
        if not branch:
            branch = 'master'
        if not module:
            module = repo
        if type(module) == str:
            module = [module]
        url = url_builder(username, repo, branch, **kw)
        return self.add_remote_repo(module, url)


    @contextmanager
    def github_repo(self, username=None, repo=None, module=None, branch=None,
                    commit=None):
        '''
    Context Manager that provides import functionality from Github repositories through HTTPS.
    The parameters are the same as the '_add_git_repo' function. No 'url_builder' function is needed.
        '''
        importer = self._add_git_repo(__create_github_url,
            username, repo, module=module, branch=branch, commit=commit)
        try:
            yield self
        except ImportError as e:
            raise e
        finally:    # Always remove the added HttpImporter from sys.meta_path 
            self.remove_remote_repo(importer)
    @contextmanager
    def bitbucket_repo(self, username=None, repo=None, module=None, branch=None,
                       commit=None):
        '''
    Context Manager that provides import functionality from BitBucket repositories through HTTPS.
    The parameters are the same as the '_add_git_repo' function. No 'url_builder' function is needed.
        '''
        importer = self._add_git_repo(__create_bitbucket_url,
            username, repo, module=module, branch=branch, commit=commit)
        try:
            yield self
        except ImportError as e:
            raise e
        finally:    # Always remove the added HttpImporter from sys.meta_path 
            self.remove_remote_repo(importer)
    @contextmanager
    def gitlab_repo(self, username=None, repo=None, module=None, branch=None,
                    commit=None, domain='gitlab.com'):
        '''
    Context Manager that provides import functionality from Github repositories through HTTPS.
    The parameters are the same as the '_add_git_repo' function. No 'url_builder' function is needed.
        '''
        importer = self._add_git_repo(__create_gitlab_url,
            username, repo, module=module, branch=branch, commit=commit, domain=domain)
        try:
            yield self
        except ImportError as e:    
            raise e
        finally:    # Always remove the added HttpImporter from sys.meta_path 
            self.remove_remote_repo(importer)
# class Importer --}

def __create_github_url(username, repo, branch='master'):
    '''
Creates the HTTPS URL that points to the raw contents of a github repository.
    '''
    github_raw_url = 'https://raw.githubusercontent.com/{user}/{repo}/{branch}/'
    return github_raw_url.format(user=username, repo=repo, branch=branch)

def __create_bitbucket_url(username, repo, branch='master'):
    '''
Creates the HTTPS URL that points to the raw contents of a bitbucket repository.
    '''
    bitbucket_raw_url = 'https://bitbucket.org/{user}/{repo}/raw/{branch}/'
    return bitbucket_raw_url.format(user=username, repo=repo, branch=branch)

def __create_gitlab_url(username, repo, branch='master', domain='gitlab.com'):
    '''
Creates the HTTPS URL that points to the raw contents of a gitlab repository.
    '''

    '''
    Gitlab returns a 308 response code for redirects,
    so the URLs have to be exact, as urllib recognises 308 as error.
    '''
    gitlab_raw_url = 'https://{domain}/{user}/{repo}/raw/{branch}'
    return gitlab_raw_url.format(user=username, repo=repo, branch=branch, domain=domain)

