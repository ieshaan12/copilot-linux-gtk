project(
  'copilot-gtk',
  version: '0.1.0',
  meson_version: '>= 0.62.0',
  default_options: ['warning_level=2'],
)

# Application ID
app_id = 'io.github.ieshaan.CopilotGTK'

# Python module
python = import('python')
py_installation = python.find_installation('python3', required: true)

# i18n
i18n = import('i18n')
gnome = import('gnome')

# Dependencies
dependency('gtk4', version: '>= 4.12')
dependency('libadwaita-1', version: '>= 1.4')

# Data files
subdir('data')

# Source files
subdir('src')

# Post-install: compile schemas, update desktop database, update icon cache
gnome.post_install(
  glib_compile_schemas: true,
  gtk_update_icon_cache: true,
  update_desktop_database: true,
)
