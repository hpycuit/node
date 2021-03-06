# Copyright 2008 the V8 project authors. All rights reserved.
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above
#       copyright notice, this list of conditions and the following
#       disclaimer in the documentation and/or other materials provided
#       with the distribution.
#     * Neither the name of Google Inc. nor the names of its
#       contributors may be used to endorse or promote products derived
#       from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import test
import os
from os.path import join, dirname, exists, splitext
import re
import ast


FLAGS_PATTERN = re.compile(r"//\s+Flags:(.*)")
FILES_PATTERN = re.compile(r"//\s+Files:(.*)")


class SimpleTestCase(test.TestCase):

  def __init__(self, path, file, arch, mode, context, config, additional=None):
    super(SimpleTestCase, self).__init__(context, path, arch, mode)
    self.file = file
    self.config = config
    self.arch = arch
    self.mode = mode
    if additional is not None:
      self.additional_flags = additional
    else:
      self.additional_flags = []


  def GetLabel(self):
    return "%s %s" % (self.mode, self.GetName())

  def GetName(self):
    return self.path[-1]

  def GetCommand(self):
    result = [self.config.context.GetVm(self.arch, self.mode)]
    source = open(self.file).read()
    flags_match = FLAGS_PATTERN.search(source)
    if flags_match:
      flags = flags_match.group(1).strip().split()
      # The following block reads config.gypi to extract the v8_enable_inspector
      # value. This is done to check if the inspector is disabled in which case
      # the '--inspect' flag cannot be passed to the node process as it will
      # cause node to exit and report the test as failed. The use case
      # is currently when Node is configured --without-ssl and the tests should
      # still be runnable but skip any tests that require ssl (which includes the
      # inspector related tests). Also, if there is no ssl support the options
      # '--use-bundled-ca' and '--use-openssl-ca' will also cause a similar
      # failure so such tests are also skipped.
      if (any(flag.startswith('--inspect') for flag in flags) and
          not self.context.v8_enable_inspector):
        print('Skipping as node was compiled without inspector support')
      elif (('--use-bundled-ca' in flags or
          '--use-openssl-ca' in flags or
          '--tls-v1.0' in flags or
          '--tls-v1.1' in flags) and
          not self.context.node_has_crypto):
        print('Skipping as node was compiled without crypto support')
      else:
        result += flags
    files_match = FILES_PATTERN.search(source);
    additional_files = []
    if files_match:
      additional_files += files_match.group(1).strip().split()
    for a_file in additional_files:
      result.append(join(dirname(self.config.root), '..', a_file))

    if self.additional_flags:
      result += self.additional_flags

    result += [self.file]

    return result

  def GetSource(self):
    return open(self.file).read()


class SimpleTestConfiguration(test.TestConfiguration):
  def __init__(self, context, root, section, additional=None):
    super(SimpleTestConfiguration, self).__init__(context, root, section)
    if additional is not None:
      self.additional_flags = additional
    else:
      self.additional_flags = []

  def Ls(self, path):
    return [f for f in os.listdir(path) if re.match('^test-.*\.m?js$', f)]

  def ListTests(self, current_path, path, arch, mode):
    all_tests = [current_path + [t] for t in self.Ls(join(self.root))]
    result = []
    for test in all_tests:
      if self.Contains(path, test):
        file_path = join(self.root, reduce(join, test[1:], ""))
        test_name = test[:-1] + [splitext(test[-1])[0]]
        result.append(SimpleTestCase(test_name, file_path, arch, mode,
                                     self.context, self, self.additional_flags))
    return result

  def GetBuildRequirements(self):
    return ['sample', 'sample=shell']

class ParallelTestConfiguration(SimpleTestConfiguration):
  def __init__(self, context, root, section, additional=None):
    super(ParallelTestConfiguration, self).__init__(context, root, section,
                                                    additional)

  def ListTests(self, current_path, path, arch, mode):
    result = super(ParallelTestConfiguration, self).ListTests(
         current_path, path, arch, mode)
    for test in result:
      test.parallel = True
    return result

class AddonTestConfiguration(SimpleTestConfiguration):
  def __init__(self, context, root, section, additional=None):
    super(AddonTestConfiguration, self).__init__(context, root, section, additional)

  def Ls(self, path):
    def SelectTest(name):
      return name.endswith('.js')

    result = []
    for subpath in os.listdir(path):
      if os.path.isdir(join(path, subpath)):
        for f in os.listdir(join(path, subpath)):
          if SelectTest(f):
            result.append([subpath, f[:-3]])
    return result

  def ListTests(self, current_path, path, arch, mode):
    all_tests = [current_path + t for t in self.Ls(join(self.root))]
    result = []
    for test in all_tests:
      if self.Contains(path, test):
        file_path = join(self.root, reduce(join, test[1:], "") + ".js")
        result.append(
            SimpleTestCase(test, file_path, arch, mode, self.context, self, self.additional_flags))
    return result

class AbortTestConfiguration(SimpleTestConfiguration):
  def __init__(self, context, root, section, additional=None):
    super(AbortTestConfiguration, self).__init__(context, root, section,
                                                 additional)

  def ListTests(self, current_path, path, arch, mode):
    result = super(AbortTestConfiguration, self).ListTests(
         current_path, path, arch, mode)
    for test in result:
      test.disable_core_files = True
    return result
