import logging, json, os, argparse, Queue

import hornet


class Hornet():


    def main(self):
        hornet.initializeLogging()

        parser = argparse.ArgumentParser(description='This is the description for hornet.py',
                                         add_help = False)
        parser.add_argument('--help',action='help',help='display this dialog')
        parser.add_argument('--config',action='store',required=True,help='JSON configuration file')
        parser.add_argument('--files',nargs='+',action='store',help=argparse.SUPPRESS)
        args = vars(parser.parse_args())
        print(str(args))
        config_path = args['config']
        files = args['files']

        hornet.log.info(' reading config file: ' + config_path)
        
        this_home = os.path.expanduser('~')
        try:
            config = json.loads(open(os.path.join(this_home, config_path)).read())
            hornet.log.debug(' Full configuration: ' + str(config))
            hornet.configureLogging(config)
        except IOError, err:
            hornet.log.critical(' The provided config file does not exist.')
            os._exit(1)
        except ValueError, err:
            hornet.log.critical(' The provided config file is invalid.')
            os._exit(1)

        # amqp and slack

        # threads used: 
        #   scheduler, classifier, watcher, mover;
        #   N nearline workers and M shippers
        nThreads = 4 + config['workers']['n-workers'] + config['shipper']['n-shippers']
        if nThreads > hornet.maxThreads:
            hornet.log.critical(' Maximum number of threads exceeded.')
            os._exit(1)
        
        queueSize = config["scheduler"]["queue-size"]
        if len(files) > queueSize:
            queueSize = len(files)
            config['scheduler']['queue-size'] = queueSize
            # change the file as well?
        
        # set up channels - TODO: controlQueue and requestQueue
        schedulingQueue = Queue.Queue(maxsize=queueSize)
        threadCountQueue = Queue.Queue(maxsize=hornet.maxThreads)

        # amqp and slack

        for f in files:
            print('Scheduling ' + f)
            schedulingQueue.put(f)



if __name__ == '__main__':
    logging.basicConfig()
    h = Hornet()
    h.main()
