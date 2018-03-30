#
# Regular cron jobs for the pipenv package
#
0 4	* * *	root	[ -x /usr/bin/pipenv_maintenance ] && /usr/bin/pipenv_maintenance
