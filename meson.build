project('handleit',
          version: '0.1.0',
    meson_version: '>= 0.50.0',
  default_options: [ 'warning_level=2',
                   ],
)

i18n = import('i18n')
python = import('python')

subdir('data')
subdir('src')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', join_paths(get_option('prefix'), get_option('localedir')))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'handleit.in',
  output: 'handleit',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir')
)

meson.add_install_script('dist/postinstall.py')
