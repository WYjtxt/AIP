# native-recorder-sync-v2
#!/usr/bin/python3
# -*- coding: utf-8 -*-

import os
import argparse
import socket
import struct
import select
import time

ICMP_ECHO_REQUEST = 8  # Platform specific
DEFAULT_TIMEOUT = 0.1
DEFAULT_COUNT = 4


class Pinger(object):
    """ Pings to a host -- the Pythonic way"""

    def __init__(self, target_host, count=DEFAULT_COUNT, timeout=DEFAULT_TIMEOUT):
        self.target_host = target_host
        self.count = count
        self.timeout = timeout

    def do_checksum(self, source_string):
        """  Verify the packet integritity """
        sum = 0
        max_count = (len(source_string) / 2) * 2
        count = 0
        while count < max_count:
            val = source_string[count + 1] * 256 + source_string[count]
            sum = sum + val
            sum = sum & 0xffffffff
            count = count + 2

        if max_count < len(source_string):
            sum = sum + ord(source_string[len(source_string) - 1])
            sum = sum & 0xffffffff

        sum = (sum >> 16) + (sum & 0xffff)
        sum = sum + (sum >> 16)
        answer = ~sum
        answer = answer & 0xffff
        answer = answer >> 8 | (answer << 8 & 0xff00)
        return answer

    def receive_pong(self, sock, ID, timeout):
        """
        Receive ping from the socket.
        """
        time_remaining = timeout
        while True:
            start_time = time.time()
            readable = select.select([sock], [], [], time_remaining)
            time_spent = (time.time() - start_time)
            if readable[0] == []:  # Timeout
                return

            time_received = time.time()
            recv_packet, addr = sock.recvfrom(1024)
            icmp_header = recv_packet[20:28]
            type, code, checksum, packet_ID, sequence = struct.unpack(
                "bbHHh", icmp_header
            )
            if packet_ID == ID:
                bytes_In_double = struct.calcsize("d")
                time_sent = struct.unpack("d", recv_packet[28:28 + bytes_In_double])[0]
                return time_received - time_sent

            time_remaining = time_remaining - time_spent
            if time_remaining <= 0:
                return

    def send_ping(self, sock, ID):
        """
        Send ping to the target host
        """
        target_addr = socket.gethostbyname(self.target_host)

        my_checksum = 0

        # Create a dummy heder with a 0 checksum.
        header = struct.pack("bbHHh", ICMP_ECHO_REQUEST, 0, my_checksum, ID, 1)
        bytes_In_double = struct.calcsize("d")
        data = (192 - bytes_In_double) * "Q"
        data = struct.pack("d", time.time()) + bytes(data.encode('utf-8'))

        # Get the checksum on the data and the dummy header.
        my_checksum = self.do_checksum(header + data)
        header = struct.pack(
            "bbHHh", ICMP_ECHO_REQUEST, 0, socket.htons(my_checksum), ID, 1
        )
        packet = header + data
        sock.sendto(packet, (target_addr, 1))

    def ping_once(self):
        """Use the ICMP protocol number; no /etc/protocols database is required."""
        started = time.monotonic()
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, 1)
            my_id = os.getpid() & 0xFFFF
            self.send_ping(sock, my_id)
            delay = self.receive_pong(sock, my_id, self.timeout)
            if delay is not None:
                return delay
        except OSError:
            pass
        finally:
            if sock is not None:
                sock.close()
        for port in (80, 8000, 554, 37777, 22):
            try:
                with socket.create_connection((self.target_host, port), timeout=max(0.1, min(float(self.timeout), 1.0))):
                    return max(time.monotonic() - started, 0.000001)
            except OSError:
                continue
        return None

    def ping(self):
        """
        Run the ping process
        """
        for i in range(self.count):
            print("Ping to %s..." % self.target_host, )
            try:
                delay = self.ping_once()
            except socket.gaierror as e:
                print("Ping failed. (socket error: '%s')" % e[1])
                break

            if delay == None:
                print("Ping failed. (timeout within %ssec.)" % self.timeout)
            else:
                delay = delay * 1000
                print("Get pong in %0.4fms" % delay)


def getRunStatus(equipment_list_ips):
    equipment_list = []
    for equipment_i in equipment_list_ips:
        pinger = Pinger(target_host=equipment_i)
        delay = pinger.ping_once()
        if delay == None:
            equipment_list.append({'ip':equipment_i,'status':2})
        else:
            equipment_list.append({'ip':equipment_i,'status':1})
    return equipment_list
