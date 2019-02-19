import os
import sys
import traceback
import time
from threading import Thread

import base
from utils import get_plugin_class, check_plugin, get_special_methods
from interfaces import has_interface
from web import WebInterfaceDispatcher

try:
    import json
except ImportError:
    import simplejson as json


class PluginRuntime:

    def __init__(self, path):
        self._stopped = False
        self._path = path.rstrip('/')

        self._input_status_receivers = []
        self._output_status_receivers = []
        self._shutter_status_receivers = []
        self._event_receivers = []

        self._name = None
        self._vesion = None
        self._interfaces = []
        self._receivers = []
        self._exposes = []
        self._metric_definitions = []
        self._metric_collectors = []
        self._metric_receivers = []

        self._plugin = None

        webinterface = WebInterfaceDispatcher(log)
        self._init_plugin(webinterface, log)
        self._start_background_tasks()

    def _init_plugin(self, webinterface, logger):
        plugin_root = os.path.dirname(self._path)
        plugin_dir = os.path.basename(self._path)

        # Add the plugin and it's eggs to the python path
        sys.path.insert(0, plugin_root)
        for egg_file in os.listdir(self._path):
            if egg_file.endswith('.egg'):
                sys.path.append(os.path.join(self._path, egg_file))

        # Expose plugins.base to the plugin
        sys.modules['plugins'] = sys.modules['__main__']
        sys.modules["plugins.base"] = base

        # Instanciate the plugin class
        plugin_class = get_plugin_class(plugin_dir)
        check_plugin(plugin_class)
        self._plugin = plugin_class(webinterface, logger)

        # Set the name, version, interfaces
        self._name = plugin_class.name
        self._version = plugin_class.version
        self._interfaces = plugin_class.interfaces

        # Set the receivers
        receiver_mapping = {'input_status': self._input_status_receivers,
                            'output_status': self._output_status_receivers,
                            'shutter_status': self._shutter_status_receivers,
                            'receive_events': self._event_receivers}

        for method_attribute, target in receiver_mapping.iteritems():
            for method in get_special_methods(self._plugin, method_attribute):
                target.append(method)

            if len(target) > 0:
                self._receivers.append(method_attribute)

        # Set the exposed methods
        for method in get_special_methods(self._plugin, 'om_expose'):
            self._exposes.append({'name': method.__name__,
                                  'auth': method.om_expose['auth'],
                                  'content_type': method.om_expose['content_type']})

        # Set the metric definitions
        if has_interface(plugin_class, 'metrics', '1.0'):
            if hasattr(plugin_class, 'metric_definitions'):
                self._metric_definitions = plugin_class.metric_definitions

        # Set the metric collectors
        for method in get_special_methods(self._plugin, 'om_metric_data'):
            self._metric_collectors.append({'name': method.__name__,
                                            'interval': method.om_metric_data['interval']})

        # Set the metric receivers
        for method in get_special_methods(self._plugin, 'om_metric_receive'):
            self._metric_receivers.append({'name': method.__name__,
                                           'source': method.om_metric_receive['source'],
                                           'metric_type': method.om_metric_receive['metric_type'],
                                           'interval': method.om_metric_receive['interval']})

    def _start_background_tasks(self):
        """ Start all background tasks. """
        tasks = get_special_methods(self._plugin, 'background_task')
        for task in tasks:
            thread = Thread(target=PluginRuntime._run_background_task, args=(task,))
            thread.name = 'Background thread ({0})'.format(task.__name__)
            thread.daemon = True
            thread.start()

    @staticmethod
    def _run_background_task(task):
        running = True
        while running:
            try:
                task()
                running = False  # Stop execution if the task returns without exception
            except Exception as exception:
                log_exception('background task', exception)
                time.sleep(30)

    def run(self):
        while not self._stopped:
            command = PluginRuntime._wait_and_read_command()
            if command is None:
                continue

            action = command['action']
            ret = None
            if action == 'start':
                ret = self._handle_start()
            elif action == 'stop':
                ret = self._handle_stop()
            elif action == 'input_status':
                ret = self._handle_input_status(command['status'])
            elif action == 'output_status':
                ret = self._handle_output_status(command['status'])
            elif action == 'shutter_status':
                ret = self._handle_shutter_status(command['status'])
            elif action == 'process_event':
                ret = self._handle_process_event(command['code'])
            elif action == 'get_metric_definitions':
                ret = self._handle_get_metric_definitions()
            elif action == 'collect_metrics':
                ret = self._handle_collect_metrics(command['name'])
            elif action == 'distribute_metric':
                ret = self._handle_distribute_metric(command['name'], command['metric'])
            elif action == 'request':
                ret = self._handle_request(command['method'], command['args'], command['kwargs'])
            elif action == 'remove_callback':
                ret = self._handle_remove_callback()
            else:
                log('Unknown action: {0}'.format(action))

            response = {'cid': command['cid'], 'action': action}
            if ret is not None:
                response.update(ret)
            write(response)

    @staticmethod
    def _wait_and_read_command():
        data = ''
        while data == '':
            data = sys.stdin.readline().strip()
        try:
            return json.loads(data)
        except ValueError:
            log('Exception in _wait_and_read_command: Could not decode stdin: {0}'.format(data))

    def _handle_start(self):
        return {'name': self._name,
                'version': self._version,
                'receivers': self._receivers,
                'exposes': self._exposes,
                'interfaces': self._interfaces,
                'metric_collectors': self._metric_collectors,
                'metric_receivers': self._metric_receivers}

    def _handle_stop(self):
        def delayed_stop():
            time.sleep(2)
            os._exit(0)

        stop_thread = Thread(target=delayed_stop)
        stop_thread.daemon = True
        stop_thread.start()

        self._stopped = True

    def _handle_input_status(self, status):
        for receiver in self._input_status_receivers:
            with_catch('input status', receiver, [status])

    def _handle_output_status(self, status):
        for receiver in self._output_status_receivers:
            with_catch('output status', receiver, [status])

    def _handle_shutter_status(self, status):
        for receiver in self._shutter_status_receivers:
            with_catch('shutter status', receiver, [status])

    def _handle_process_event(self, code):
        for receiver in self._event_receivers:
            with_catch('process event', receiver, [code])

    def _handle_get_metric_definitions(self):
        return {'metric_definitions': self._metric_definitions}

    def _handle_collect_metrics(self, name):
        metrics = []
        collect = getattr(self._plugin, name)
        try:
            metrics.extend(list(collect()))
        except Exception as exception:
            log_exception('collect metrics', exception)
        return {'metrics': metrics}

    def _handle_distribute_metric(self, name, metric):
        receive = getattr(self._plugin, name)
        with_catch('distribute metric', receive, [metric])

    def _handle_request(self, method, args, kwargs):
        func = getattr(self._plugin, method)
        try:
            return {'success': True, 'response': func(*args, **kwargs)}
        except Exception as exception:
            return {'success': False, 'exception': str(exception), 'stacktrace': traceback.format_exc()}

    def _handle_remove_callback(self):
        for method in get_special_methods(self._plugin, 'on_remove'):
            try:
                method()
            except Exception as exception:
                log_exception('on remove', exception)


def log(msg):
    write({'cid': 0, 'action': 'logs', 'logs': str(msg)})


def log_exception(name, exception):
    log('Exception ({0}) in {1}: {2}'.format(exception, name, traceback.format_exc()))


def with_catch(name, target, args):
    """ Logs Exceptions that happen in target(*args). """
    try:
        return target(*args)
    except Exception as exception:
        log_exception(name, exception)


def write(msg):
    sys.stdout.write(json.dumps(msg) + '\n')
    sys.stdout.flush()


def print_usage():
    sys.stderr.write('Usage: python {0} start <path>\n'.format(sys.argv[0]))


def watch_parent():
    parent = os.getppid()
    # If the parent process gets kills, this process will be attached to init.
    # In that case the plugin should stop running.
    while True:
        if os.getppid() != parent:
            os._exit(1)
        time.sleep(1)


if __name__ == '__main__':
    if len(sys.argv) < 3 or sys.argv[1] != 'start':
        print_usage()
        sys.exit(1)

    # Keep an eye on our parent process
    watcher = Thread(target=watch_parent)
    watcher.daemon = True
    watcher.start()

    # Start the runtime
    try:
        pr = PluginRuntime(path=sys.argv[2])
        pr.run()
    except BaseException as ex:
        log_exception('__main__', ex)
        os._exit(1)

    os._exit(0)
