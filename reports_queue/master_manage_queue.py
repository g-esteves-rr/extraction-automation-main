import fcntl
import os
import subprocess
import sys
import time
import logging

# Configure logging
logging.basicConfig(
    filename='/root/Desktop/extraction-automation-main/reports_queue/manage_queue.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Path to the semaphore file
semaphore_file = '/root/Desktop/extraction-automation-main/reports_queue/manage_queue.lock'
lock_timeout = 600  # Timeout in seconds (10 minutes)

# Function to acquire the semaphore
def acquire_semaphore(timeout):
    start_time = time.time()
    fd = None
    while time.time() - start_time < timeout:
        try:
            fd = os.open(semaphore_file, os.O_CREAT | os.O_RDWR)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logging.info('Semaphore acquired.')
            print('Semaphore acquired.')
            return fd
        except BlockingIOError:
            elapsed_time = time.time() - start_time
            if int(elapsed_time) % 60 == 0:  # Print and log every minute
                logging.info(f'Waiting for semaphore... {int(elapsed_time)} seconds elapsed.')
                print(f'Waiting for semaphore... {int(elapsed_time)} seconds elapsed.')
            time.sleep(1)  # Wait for 1 second before retrying
    return None

# Function to release the semaphore
def release_semaphore(fd):
    if fd:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        logging.info('Semaphore released.')
        print('Semaphore released.')

# Main function
def main():
    logging.info('Starting master_manage_queue.py')
    print('Starting master_manage_queue.py')

    fd = acquire_semaphore(lock_timeout)
    if fd is None:
        logging.info('Semaphore is already locked and timeout reached. Exiting.')
        print('Semaphore is already locked and timeout reached. Exiting.')
        sys.exit(0)
    
    try:
        # Run the manage_queue.sh script
        result = subprocess.run(['/root/Desktop/extraction-automation-main/reports_queue/manage_queue.sh'], capture_output=True, text=True)
        if result.returncode == 0:
            logging.info('Script manage_queue.sh executed successfully.')
            print('Script manage_queue.sh executed successfully.')
        else:
            logging.error(f'Script manage_queue.sh failed with return code {result.returncode}. Output: {result.stdout} Error: {result.stderr}')
            print(f'Script manage_queue.sh failed with return code {result.returncode}. Output: {result.stdout} Error: {result.stderr}')
    except Exception as e:
        logging.error(f'Error running manage_queue.sh: {str(e)}')
        print(f'Error running manage_queue.sh: {str(e)}')
    finally:
        release_semaphore(fd)
        logging.info('Exiting manage_queue.py')
        print('Exiting manage_queue.py')

if __name__ == '__main__':
    main()
