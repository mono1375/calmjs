# -*- coding: utf-8 -*-
import logging
import unittest
import json
import os
import sys
from os.path import join
from os.path import exists

from distutils.errors import DistutilsOptionError
from setuptools.dist import Distribution
import pkg_resources

from calmjs.command import distutils_log_handler

from calmjs import cli
from calmjs.testing.utils import make_dummy_dist
from calmjs.testing.utils import mkdtemp
from calmjs.testing.utils import stub_mod_call
from calmjs.testing.utils import stub_dist_flatten_package_json
from calmjs.testing.utils import stub_stdouts


class DistLoggerTestCase(unittest.TestCase):
    """
    Test for the adapter from standard logging to the distutils version.
    """

    def setUp(self):
        stub_stdouts(self)

    def tearDown(self):
        distutils_log_handler.log.set_threshold(distutils_log_handler.log.WARN)

    def test_logging_bad(self):
        logger = logging.getLogger('calmjs.testing.dummy')
        logger.setLevel(logging.DEBUG)
        distutils_log_handler.log.set_verbosity(0)
        logger.addHandler(distutils_log_handler)
        logger.log(9001, 'Over 9000 will definitely not work')
        self.assertEqual(sys.stdout.getvalue(), '')
        value = sys.stderr.getvalue()
        self.assertTrue(sys.stderr.getvalue().startswith(
            'Failed to convert <LogRecord: calmjs.testing.dummy, 9001'))

    def test_logging_all(self):
        logger = logging.getLogger('calmjs.testing.dummy')
        logger.setLevel(logging.DEBUG)
        distutils_log_handler.log.set_verbosity(2)
        logger.addHandler(distutils_log_handler)
        logger.critical('Critical')
        logger.error('Error')
        logger.warning('Warning')
        logger.info('Information')
        logger.debug('Debug')
        self.assertEqual(sys.stderr.getvalue(), 'Critical\nError\nWarning\n')
        self.assertEqual(sys.stdout.getvalue(), 'Information\nDebug\n')

    def test_logging_info_only(self):
        logger = logging.getLogger('calmjs.testing.dummy')
        logger.setLevel(logging.DEBUG)
        distutils_log_handler.log.set_verbosity(1)
        logger.addHandler(distutils_log_handler)
        logger.info('Information')
        logger.debug('Debug')
        self.assertEqual(sys.stdout.getvalue(), 'Information\n')

    def test_logging_errors_only(self):
        logger = logging.getLogger('calmjs.testing.dummy')
        logger.setLevel(logging.DEBUG)
        distutils_log_handler.log.set_verbosity(0)
        logger.addHandler(distutils_log_handler)
        logger.info('Information')
        logger.debug('Debug')
        logger.warning('Warning')
        self.assertEqual(sys.stdout.getvalue(), '')
        self.assertEqual(sys.stderr.getvalue(), 'Warning\n')


class DistCommandTestCase(unittest.TestCase):
    """
    Test case for the commands within.
    """

    def setUp(self):
        self.cwd = os.getcwd()

        app = make_dummy_dist(self, (
            ('requires.txt', '\n'.join([])),
            ('package.json', json.dumps({
                'dependencies': {'jquery': '~1.11.0'},
            })),
        ), 'foo', '1.9.0')

        working_set = pkg_resources.WorkingSet()
        working_set.add(app, self._calmjs_testing_tmpdir)

        # Stub out the flatten_package_json calls with one that uses our
        # custom working_set here.
        stub_dist_flatten_package_json(self, [cli], working_set)
        # Quiet stdout from distutils logs
        stub_stdouts(self)

    def tearDown(self):
        os.chdir(self.cwd)

    def test_no_args(self):
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm'],
            name='foo',
        ))
        dist.parse_command_line()
        with self.assertRaises(DistutilsOptionError):
            dist.run_commands()

    def test_init_no_overwrite(self):
        tmpdir = mkdtemp(self)

        with open(os.path.join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {}, 'devDependencies': {}}, fd)

        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--init'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # gets overwritten anyway.
        self.assertEqual(result, {
            'dependencies': {},
            'devDependencies': {},
        })

    def test_init_overwrite(self):
        tmpdir = mkdtemp(self)

        with open(os.path.join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {}, 'devDependencies': {}}, fd)

        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--init', '--overwrite'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # gets overwritten anyway.
        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
        })

    def test_init_merge(self):
        tmpdir = mkdtemp(self)

        with open(os.path.join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({'dependencies': {
                'underscore': '~1.8.0',
            }, 'devDependencies': {
                'sinon': '~1.17.0',
            }}, fd)

        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--init', '--merge'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # gets overwritten anyway.
        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0', 'underscore': '~1.8.0'},
            'devDependencies': {'sinon': '~1.17.0'},
        })

    def test_install_no_init(self):
        stub_mod_call(self, cli)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--install'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # The cli will still automatically write to that.
        self.assertEqual(result, {
            'dependencies': {'jquery': '~1.11.0'},
            'devDependencies': {},
        })
        self.assertEqual(self.call_args, ((['npm', 'install'],), {}))

    def test_install_no_init_has_package_json(self):
        stub_mod_call(self, cli)
        tmpdir = mkdtemp(self)

        with open(os.path.join(tmpdir, 'package.json'), 'w') as fd:
            json.dump({
                'dependencies': {'jquery': '~3.0.0'},
                'devDependencies': {}
            }, fd)

        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--install'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        with open(os.path.join(tmpdir, 'package.json')) as fd:
            result = json.load(fd)

        # Existing package.json will not be overwritten.
        self.assertEqual(result, {
            'dependencies': {'jquery': '~3.0.0'},
            'devDependencies': {},
        })

    def test_install_false(self):
        stub_mod_call(self, cli)
        tmpdir = mkdtemp(self)
        os.chdir(tmpdir)
        dist = Distribution(dict(
            script_name='setup.py',
            script_args=['npm', '--install', '--dry-run'],
            name='foo',
        ))
        dist.parse_command_line()
        dist.run_commands()

        self.assertFalse(exists(join(tmpdir, 'package.json')))
        self.assertIsNone(self.call_args)