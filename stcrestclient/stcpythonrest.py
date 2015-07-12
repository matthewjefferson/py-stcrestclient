"""
ReST API adapter for StcPython.py

Allow Python automation clients to change from using client BLL to STC ReST API
without having to make any code changes.

"""
from __future__ import absolute_import
from __future__ import print_function

import os
import time
import atexit

try:
    from . import stchttp
except ValueError:
    import stchttp


class StcPythonRest(object):

    """
    StcPythonRest is a substitute for StcPython that uses the STC ReST API.

    """

    def __init__(self):
        self._stc = None
        atexit.register(self._end_session)

    def apply(self):
        self._check_session()
        return self._stc.apply()

    def config(self, _object, **kwargs):
        self._check_session()
        return self._stc.config(_object, kwargs)

    def connect(self, *hosts):
        self._check_session()
        svec = StcPythonRest._unpack_args(*hosts)
        return self._stc.connect(svec)

    def create(self, _type, **kwargs):
        self._check_session()
        under = None
        if _type != 'project':
            under = kwargs.pop('under')
        return self._stc.create(_type, under, kwargs)

    def delete(self, handle):
        self._check_session()
        return self._stc.delete(handle)

    def disconnect(self, *hosts):
        self._check_session()
        svec = StcPythonRest._unpack_args(*hosts)
        return self._stc.disconnect(svec)

    def get(self, handle, *args):
        self._check_session()
        svec = StcPythonRest._unpack_args(*args)
        return self._stc.get(handle, *svec)

    def help(self, topic=None):
        if not topic or ' ' in topic:
            return 'Usage: \n' + \
                   '  stc.help(\'commands\')\n' + \
                   '  stc.help(<handle>)\n' + \
                   '  stc.help(<className>)\n' + \
                   '  stc.help(<subClassName>)'

        if topic == 'commands':
            return '\n'.join(sorted((
                cmd_help['desc']
                for cmd_help in self._HELP_INFO.itervalues())))

        info = self._HELP_INFO.get(topic)
        if info:
            return 'Desc: %s\nUsage: %s\nExample: %s\n' % (
                info['desc'], info['usage'], info['example'])

        self._check_session()
        return self._stc.help(topic)

    def log(self, level, msg):
        self._check_session()
        return self._stc.log(level, msg)

    def perform(self, _cmd, **kwargs):
        self._check_session()
        cmd = _cmd.lower()
        if cmd == 'cssynchronizefiles':
            self._stc.download_all()
            return

        if cmd == 'cstestsessiondisconnect':
            kill = False
            for k in kwargs:
                if k.lower() == 'terminate':
                    kill = _is_true(kwargs[k])
                    break
            self._end_session(kill)
            return

        if cmd == 'cstestsessionconnect':
            host = None
            new = False
            u_name = None
            s_name = None
            for k in kwargs:
                kl = k.lower()
                if kl == 'host':
                    host = kwargs[k]
                elif kl == 'createnewtestsession':
                    new = _is_true(kwargs[k])
                elif kl == 'testsessionname':
                    s_name = kwargs[k]

            if not new and not s_name:
                raise ValueError('missing TestSessionName')

            self._end_session()
            self._new_session(host, s_name, u_name)
            return

        return self._stc.perform(_cmd, kwargs)

    def sleep(self, seconds):
        time.sleep(seconds)

    def waitUntilComplete(self, **kwargs):
        self._check_session()
        ret = self._stc.wait_until_complete(int(kwargs.get('timeout', 0)))
        if os.environ.get('STC_SESSION_SYNCFILES_ON_SEQ_COMPLETE') == '1':
            self._stc.download_all()

        return ret

    def release(self, *csps):
        self._check_session()
        svec = StcPythonRest._unpack_args(*csps)
        self._stc.perform('releasePort', {'Location': ' '.join(svec)})

    def reserve(self, *csps):
        self._check_session()
        svec = StcPythonRest._unpack_args(*csps)
        self._stc.perform('reservePort', {'Location': ' '.join(svec)})

    def subscribe(self, **kwargs):
        self._check_session()
        data = self._stc.perform('ResultsSubscribe', kwargs)
        return data.get('ReturnedResultDataSet')

    def unsubscribe(self, rdsHandle):
        self._check_session()
        self._stc.perform('ResultDataSetUnsubscribe',
                          {'ResultDataSet': rdsHandle})

    def _check_session(self):
        """Start a new session if one is not already started."""
        if not self._stc:
            self._new_session()

    def _new_session(self, server=None, session_name=None, user_name=None):
        """Create a new session or attach to existing."""
        if not server:
            server = os.environ.get('STC_SERVER_ADDRESS')
            if not server:
                raise EnvironmentError('STC_SERVER_ADDRESS not set')
        self._stc = stchttp.StcHttp(server)
        if not session_name:
            session_name = os.environ.get('STC_SESSION_NAME')
            if not session_name or session_name == '__NEW_TEST_SESSION__':
                session_name = None
        self._stc.new_session(user_name, session_name)

    def _end_session(self, kill=None):
        """End the client session."""
        if self._stc:
            if kill is None:
                kill = os.environ.get('STC_SESSION_TERMINATE_ON_DISCONNECT')
                kill = _is_true(kill)
            self._stc.end_session(kill)
            self._stc = None

    _HELP_INFO = dict(
        create=dict(
            desc="create: -Creates an object in a test hierarchy",
            usage=("stc.create(className, under = parentObjectHandle, "
                   "propertyName1 = propertyValue1, ...)"),
            example=('stc.create(\'port\', under=\'project1\', location = '
                     '"#{mychassis1}/1/2")')
            ),
        config=dict(
            desc="config: -Sets or modifies the value of an attribute",
            usage=("stc.config(objectHandle, propertyName1 = propertyValue1, "
                   "...)"),
            example="stc.config(stream1, enabled = true)"
            ),
        get=dict(
            desc="get: -Retrieves the value of an attribute",
            usage="stc.get(objectHandle, propertyName1, propertyName2, ...)",
            example="stc.get(stream1, 'enabled', 'name')"
            ),
        perform=dict(
            desc="perform: -Invokes an operation",
            usage=("stc.perform(commandName, propertyName1 = propertyValue1, "
                   "...)"),
            example=("stc.perform('createdevice', parentHandleList = "
                     "'project1' createCount = 4)")
            ),
        delete=dict(
            desc="delete: -Deletes an object in a test hierarchy",
            usage="stc.delete(objectHandle)",
            example="stc.delete(stream1)"),

        connect=dict(
            desc=("connect: -Establishes a connection with a Spirent "
                  "TestCenter chassis"),
            usage="stc.connect(hostnameOrIPaddress, ...)",
            example="stc.connect(mychassis1)"
            ),
        disconnect=dict(
            desc=("disconnect: -Removes a connection with a Spirent "
                  "TestCenter chassis"),
            usage="stc.disconnect(hostnameOrIPaddress, ...)",
            example="stc.disconnect(mychassis1)"
            ),
        reserve=dict(
            desc="reserve: -Reserves a port group",
            usage="stc.reserve(CSP1, CSP2, ...)",
            example='stc.reserve("//#{mychassis1}/1/1", "//#{mychassis1}/1/2")'
            ),
        release=dict(
            desc="release: -Releases a port group",
            usage="stc.release(CSP1, CSP2, ...)",
            example='stc.release("//#{mychassis1}/1/1", "//#{mychassis1}/1/2")'
            ),
        apply=dict(
            desc=("apply: -Applies a test configuration to the Spirent "
                  "TestCenter firmware"),
            usage="stc.apply()",
            example="stc.apply()"
            ),
        log=dict(
            desc="log: -Writes a diagnostic message to the log file",
            usage="stc.log(logLevel, message)",
            example="stc.log('DEBUG', 'This is a debug message')"
            ),
        waitUntilComplete=dict(
            desc=("waitUntilComplete: -Suspends your application until the "
                  "test has finished"),
            usage="stc.waitUntilComplete()",
            example="stc.waitUntilComplete()"
            ),
        subscribe=dict(
            desc=("subscribe: -Directs result output to a file or to "
                  "standard output"),
            usage=("stc.subscribe(parent=parentHandle, "
                   "resultParent=parentHandles, configType=configType, "
                   "resultType=resultType, viewAttributeList=attributeList, "
                   "interval=interval, fileNamePrefix=fileNamePrefix)"),
            example=("stc.subscribe(parent='project1', "
                     "configType='Analyzer', "
                     "resulttype='AnalyzerPortResults', "
                     "filenameprefix='analyzer_port_counter')")
            ),
        unsubscribe=dict(
            desc="unsubscribe: -Removes a subscription",
            usage="stc.unsubscribe(resultDataSetHandle)",
            example="stc.unsubscribe(resultDataSet1)"))

    @staticmethod
    def _unpack_args(*args):
         svec = []
         for arg in args:
            if isinstance(arg, (list, tuple)):
                svec.extend(arg)
            else:
                svec.append(arg)
         return svec


def _is_true(val):
    return val in (True, 1, '1', 'TRUE', 'True', 'true')