# -*- coding: utf-8 -*-
#
# Syncano documentation build configuration file, created by
# sphinx-quickstart on Mon Feb 23 13:51:24 2015.
#
# This file is execfile()d with the current directory set to its
# containing dir.
#
# Note that not all possible configuration values are present in this
# autogenerated file.
#
# All configuration values have a default; values that are commented out
# serve to show the default.
from __future__ import unicode_literals

import sys
from os.path import abspath, dirname

import sphinx_rtd_theme

sys.path.insert(1, dirname(dirname(dirname(abspath(__file__)))))

needs_sphinx = '1.0'
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.viewcode',
]

if 'spelling' in sys.argv:
    extensions.append("sphinxcontrib.spelling")

spelling_lang = 'en_US'
templates_path = ['_templates']
source_suffix = '.rst'
# source_encoding = 'utf-8-sig'
master_doc = 'index'
project = 'Syncano'
copyright = 'Syncano Inc'
version = '4.0.0'
release = '4.0.0'
# language = None
# today = ''
# today_fmt = '%B %d, %Y'
exclude_patterns = ['_build', '**tests**', 'build', 'setup.py', 'run_it.py']
# default_role = None
add_function_parentheses = True
add_module_names = False
# show_authors = False
pygments_style = 'sphinx'
# modindex_common_prefix = ['syncano.']
# keep_warnings = False

html_theme = 'sphinx_rtd_theme'
html_theme_options = {}
html_theme_path = [sphinx_rtd_theme.get_html_theme_path()]
# html_title = None
# html_short_title = None
# html_logo = None
# html_favicon = None
html_static_path = ['_static']
# html_extra_path = []
# html_last_updated_fmt = '%b %d, %Y'
# html_use_smartypants = True
# html_sidebars = {}
# html_additional_pages = {}
# html_domain_indices = True
# html_use_index = True
# html_split_index = False
# html_show_sourcelink = True
# html_show_sphinx = True
# html_show_copyright = True
# html_use_opensearch = ''
# html_file_suffix = None
htmlhelp_basename = 'Syncanodoc'

latex_elements = {}
latex_documents = [(
    'index', 'Syncano.tex',
    'Syncano Documentation',
    'Syncano', 'manual'
)]
# latex_logo = None
# latex_use_parts = False
# latex_show_pagerefs = False
# latex_show_urls = False
# latex_appendices = []
# latex_domain_indices = True

man_pages = [
    ('index', 'syncano', 'Syncano Documentation',
     ['Syncano'], 1)
]
# man_show_urls = False

texinfo_documents = [(
    'index', 'Syncano', 'Syncano Documentation',
    'Syncano', 'Syncano', 'One line description of project.',
    'Miscellaneous'
)]

# texinfo_appendices = []
# texinfo_domain_indices = True
# texinfo_show_urls = 'footnote'
# texinfo_no_detailmenu = False

autodoc_member_order = 'bysource'
highlight_language = 'python'
