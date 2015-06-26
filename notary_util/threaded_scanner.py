#   This file is part of the Perspectives Notary Server
#
#   Copyright (C) 2011 Dan Wendlandt
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation, version 3 of the License.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Scan a list of services and update Observation records in the notary database.
For running scans without connecting to the database see util/simple_scanner.py.
"""

import argparse
import errno
import logging
import os
import sys
import threading
import time 
import traceback 

import notary_common
from notary_db import ndb

# TODO: HACK
# add ..\util to the import path so we can import ssl_scan_sock
sys.path.insert(0,
	os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from util.ssl_scan_sock import attempt_observation_for_service, SSLScanTimeoutException, SSLAlertException
from util.ssl_scan_openssl import openssl_attempt_observation_for_service
# +cache
from util import cache

DEFAULT_SCANS = 10
DEFAULT_WAIT = 20
DEFAULT_INFILE = "-"

# +cache
DEFAULT_REDIS_ADDR='redis://127.0.0.1'
DEFAULT_MEMCACHED_ADDR='tcp:127.0.0.1'
MEMCACHED_ANON_AUTH_MODE=False



# TODO: more fine-grained error accounting to distinguish different failures
# (dns lookups, conn refused, timeouts).  Particularly interesting would be
# those that fail or hang after making some progress, as they could indicate
# logic bugs

class ScanThread(threading.Thread): 

	def __init__(self, sid, global_stats,timeout_sec, sni, cache = None, use_openssl_flag = False):
		self.sid = sid
		self.global_stats = global_stats
		self.global_stats.active_threads += 1
		threading.Thread.__init__(self)
		self.timeout_sec = timeout_sec
		self.sni = sni
		self.global_stats.threads[sid] = time.time() 
		self.cache=cache
		self.use_openssl=use_openssl_flag

	def get_errno(self, e): 
		try: 
			return e.args[0]
		except: 
			return 0 # no error

	def record_failure(self, e,): 
		stats.failures += 1
		ndb.report_metric('ServiceScanFailure', str(e))
		if (isinstance(e, SSLScanTimeoutException)):
			stats.failure_timeouts += 1
			return
		if (isinstance(e, SSLAlertException)):
			stats.failure_ssl_alert += 1
			return
		if (isinstance(e, ValueError)):
			stats.failure_other += 1
			return

		err = self.get_errno(e) 
		if err == errno.ECONNREFUSED or err == errno.EINVAL:
			stats.failure_conn_refused += 1
		elif err == errno.EHOSTUNREACH or err == errno.ENETUNREACH: 
			stats.failure_no_route += 1
		elif err == errno.ECONNRESET: 
			stats.failure_conn_reset += 1
		elif err == -2 or err == -3 or err == -5 or err == 8: 
			stats.failure_dns += 1
		else: 	
			stats.failure_other += 1 
			logging.error("Unknown error scanning '%s'\n" % self.sid)
			traceback.print_exc(file=sys.stdout)

	def do_openssl(self):
		try:
			fp = openssl_attempt_observation_for_service(self.sid, self.timeout_sec, self.sni)
			if (fp != None):
				res_list.append((self.sid,fp))
				if (self.cache):
				    self.cache.destroy(self.sid);
			else:
				# error already logged, but tally error count <--- final error
				stats.failures += 1
				stats.failure_socket += 1
		except Exception as e:
			traceback.print_exc(file=sys.stdout)
			self.record_failure(e)

	def run(self): 
		try:
			if(self.use_openssl):
			    fp = openssl_attempt_observation_for_service(self.sid, self.timeout_sec, self.sni)
			else:
			    fp = attempt_observation_for_service(self.sid, self.timeout_sec, self.sni)
			if (fp != None):
				res_list.append((self.sid,fp))
				if (self.cache):
				    self.cache.destroy(self.sid);
			#else: <---- Let's gie OpenSSL a try
				# error already logged, but tally error count
				#stats.failures += 1
				#stats.failure_socket += 1
		except Exception, e:
			if(self.use_openssl):
			    logging.error("Error scanning '{0}' - {1}".format(self.sid, e))
			else:
			    logging.error("Error scanning '{0}' - {1}, trying OpenSSL".format(self.sid, e))
			    self.do_openssl();
		self.global_stats.num_completed += 1
		self.global_stats.active_threads -= 1
		
		del self.global_stats.threads[self.sid]

class GlobalStats(): 


	def __init__(self): 
		self.failures = 0
		self.num_completed = 0
		self.active_threads = 0 
		self.num_started = 0 
		self.threads = {} 

		# individual failure counts
		self.failure_timeouts = 0
		self.failure_no_route = 0
		self.failure_conn_refused = 0
		self.failure_conn_reset = 0
		self.failure_dns = 0 
		self.failure_ssl_alert = 0
		self.failure_socket = 0
		self.failure_other = 0 


	

def record_observations_in_db(res_list): 
	if len(res_list) == 0: 
		return
	try: 
		for r in res_list: 
			ndb.report_observation(r[0], r[1])
	except:
		# TODO: we should probably retry here 
		logging.critical("DB Error: Failed to write res_list of length %s" % \
					len(res_list))
		traceback.print_exc(file=sys.stdout)


# +cache
def cache_duration(self, value):
	"""Validate cache duration time, or raise an exception if we cannot."""
	# let the user specify durations in seconds, minutes, or hours
	if (re.search("[^0-9SsMmHh]+", value) != None):
		raise argparse.ArgumentTypeError("Invalid cache duration '{0}'.".format(value))

	# remove non-numeric characters
	duration = value.translate(None, 'SsMmHh')
	duration = int(duration)

	time_units = 0
	if (re.search("[Ss]", value)):
		time_units += 1
	if (re.search("[Mm]", value)):
		time_units += 1
		duration *= 60
	if (re.search("[Hh]", value)):
		time_units += 1
		duration *= 3600

	if (time_units > 1):
		raise argparse.ArgumentTypeError("Only specify one of [S|M|H] for cache duration.")
	elif (time_units == 0):
		duration *= 3600 # assume hours by default

	if (duration < 1):
		raise argparse.ArgumentTypeError("Cache duration must be at least 1 second.")

	return duration



parser = argparse.ArgumentParser(parents=[ndb.get_parser()],
description=__doc__)

parser.add_argument('service_id_file', type=argparse.FileType('r'), nargs='?', default=DEFAULT_INFILE,
			help="File that contains a list of service names - one per line. Will read from stdin by default.")
parser.add_argument('--scans', '--scans-per-sec', '-s', nargs='?', default=DEFAULT_SCANS, const=DEFAULT_SCANS, type=int,
			help="How many scans to run per second. Default: %(default)s.")
parser.add_argument('--timeout', '--wait', '-w', nargs='?', default=DEFAULT_WAIT, const=DEFAULT_WAIT, type=int,
			help="Maximum number of seconds each scan will wait (asychronously) for results before giving up. Default: %(default)s.")
parser.add_argument('--sni', action='store_true', default=False,
			help="use Server Name Indication. See section 3.1 of http://www.ietf.org/rfc/rfc4366.txt.\
			Default: \'%(default)s\'")
loggroup = parser.add_mutually_exclusive_group()
loggroup.add_argument('--verbose', '-v', default=False, action='store_true',
			help="Verbose mode. Print more info about each scan.")
loggroup.add_argument('--quiet', '-q', default=False, action='store_true',
			help="Quiet mode. Only print system-critical problems.")

# +cache
cachegroup = parser.add_mutually_exclusive_group()
cachegroup.add_argument('--memcache', '--memcached', action='store_true', default=False,help="Use memcache to cache observation data, to increase performance and reduce load on the notary database.")
cachegroup.add_argument('--memcachier', action='store_true', default=False,help="Use memcachier to cache observation data. " + cache.Memcachier.get_help())
cachegroup.add_argument('--redis', action='store_true', default=False,help="Use redis to cache observation data. " + cache.Redis.get_help())
memcachedgroup = parser.add_mutually_exclusive_group()
memcachedgroup.add_argument('--memcache-host','-mh', default=DEFAULT_MEMCACHED_ADDR, help="Address to use for the memcached connection. Default: \'%(default)s\' or use environment vars if not specified explicitly.")
memcachedgroup.add_argument('--envmemcache', action='store_true', default=False, help="Get all the memcached details out of environment variables(default behaviour)")
parser.add_argument('--memcache-user','-mu', help="Memcached username. Default: use environment vars if no host specified.")
parser.add_argument('--memcache-password', '-mp', help="Memcached password. Default: use environment vars if no host specified.")
parser.add_argument('--memcache-anonymous-mode', default=MEMCACHED_ANON_AUTH_MODE, help="Set this flag if memcached does not require an authentication.  Default: \'%(default)s\'")
parser.add_argument('--redis-url', '-ru', default=DEFAULT_REDIS_ADDR, help="Address to use for the redis backend. Default: \'%(default)s\'.")
parser.add_argument('--openssl-only',action='store_true',default=True,help="Use binary OpenSSL only. Default: \'%(default)s\'.")

args = parser.parse_args()

# pass ndb the args so it can use any relevant ones from its own parser
ndb = ndb(args)

loglevel = logging.WARNING
if (args.verbose):
	loglevel = logging.INFO
elif (args.quiet):
	loglevel = logging.CRITICAL
logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=loglevel)

# +cache
cacheJar = None
if (args.memcache):
    if(args.envmemcache):
	print "Creating memcache via pylibmc from environment"
	cacheJar = cache.Memcache()
    else:
	print "Creating memcache via pylibmc with host specified %s" % args.memcache_host
	if(args.memcache_anonymous_mode):
	    print "Anonymous mode selected for memcached"
	    cacheJar = cache.Memcache(args.memcache_host,'','',True)
	else:
	    print "User credentials must be supplied"
	    if(args.memcache_user and args.memcache_password):
		print "Using username %s for memcached" % args.memcache_user
		cacheJar = cache.Memcache(args.memcache_host,args.memcache_user,args.memcache_password)
	    else:
		print "Authentication is required for memcached, but no username and password pair was specified, will take them out of env vars"
		cacheJar = cache.Memcache(args.memcache_host)
elif (args.memcachier):
    if(args.envmemcache):
	print "Creating memcache via Memcachier from environment"
	cacheJar = cache.Memcachier()
    else:
	print "Creating memcache via Memcachier with host specified %s" % args.memcache_host
	if(args.memcache_anonymous_mode):
	    print "Anonymous mode selected for memcached"
	    cacheJar = cache.Memcachier(args.memcache_host,'','',True)
	else:
	    print "User credentials must be supplied"
	    if(args.memcache_user and args.memcache_password):
		print "Using username %s for memcached" % args.memcache_user
		cacheJar = cache.Memcachier(args.memcache_host,args.memcache_user,args.memcache_password)
	    else:
		print "Authentication is required for memcached, but no username and password pair was specified, will take them out of env vars"
		cacheJar = cache.Memcachier(args.memcache_host)
elif (args.redis):
	cacheJar = cache.Redis(args.redis_url)


res_list = [] 
stats = GlobalStats()
rate = args.scans
timeout_sec = args.timeout
f = args.service_id_file
start_time = time.time()
localtime = time.asctime( time.localtime(start_time) )

if(args.openssl_only):
    use_openssl=True
else:
    use_openssl=False

# read all service names to start;
# otherwise the database can lock up
# if we're accepting data piped from another process
all_sids = [ line.rstrip() for line in f ]

print "Starting scan of %s service-ids at: %s" % (len(all_sids), localtime)
print "INFO: *** Timeout = %s sec  Scans-per-second = %s" % \
    (timeout_sec, rate) 
ndb.report_metric('ServiceScanStart', "ServiceCount: " + str(len(all_sids)))

for sid in all_sids:  
	try: 
		# ignore non SSL services
		# TODO: use a regex instead
		if sid.split(",")[1] == notary_common.SSL_TYPE:
			stats.num_started += 1
			t = ScanThread(sid,stats,timeout_sec,args.sni,cacheJar,use_openssl)
			t.start()
 
		if (stats.num_started % rate) == 0: 
			time.sleep(1)
			record_observations_in_db(res_list) 
			res_list = [] 
			so_far = int(time.time() - start_time)
			logging.info("%s seconds passed.  %s complete, %s " \
				"failures.  %s Active threads" % \
				(so_far, stats.num_completed,
				stats.failures, stats.active_threads))
			logging.info("  details: timeouts = %s, " \
				"ssl-alerts = %s, no-route = %s, " \
				"conn-refused = %s, conn-reset = %s,"\
				"dns = %s, socket = %s, other = %s" % \
				(stats.failure_timeouts,
				stats.failure_ssl_alert,
				stats.failure_no_route,
				stats.failure_conn_refused,
				stats.failure_conn_reset,
				stats.failure_dns,
				stats.failure_socket,
				stats.failure_other))

		if stats.num_started  % 1000 == 0: 
			if (args.verbose):
				logging.info("long running threads")
				cur_time = time.time()
				for sid in stats.threads.keys():
					spawn_time = stats.threads.get(sid,cur_time)
					duration = cur_time - spawn_time
					if duration > 20:
						logging.info("'%s' has been running for %s" %\
						 (sid,duration))

	except IndexError:
		logging.error("Service '%s' has no index [1] after splitting on ','.\n" % (sid))
	except KeyboardInterrupt: 
		exit(1)	

# finishing the for-loop means we kicked-off all threads, 
# but they may not be done yet.  Wait for a bit, if needed.
giveup_time = time.time() + (2 * timeout_sec) 
while stats.active_threads > 0: 
	time.sleep(1)
	if time.time() > giveup_time: 
		break

# record any observations made since we finished the
# main for-loop			
record_observations_in_db(res_list)

duration = int(time.time() - start_time)
localtime = time.asctime( time.localtime(start_time) )
print "Ending scan at: %s" % localtime
print "Scan of %s services took %s seconds.  %s Failures" % \
	(stats.num_started,duration, stats.failures)
ndb.report_metric('ServiceScanStop')
exit(0) 
