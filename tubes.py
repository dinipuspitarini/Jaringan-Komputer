#!/usr/bin/python
from mininet.net import Mininet
from mininet.topo import Topo
from mininet.node import Node
from mininet.log import setLogLevel
from mininet.cli import CLI
from mininet.link import TCLink
from datetime import datetime
import time
import os
import subprocess

class LinuxRouter(Node):
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd('sysctl net.ipv4.ip_forward=1')

    def terminate(self):
        self.cmd('sysctl net.ipv4.ip_forward=0')
        super(LinuxRouter, self).terminate()

#Membangun topologi
class myTopo(Topo):
    def build(self, **_opts):
        #Membuat objek host A dan host B
        hostA = self.addHost('hostA', ip='172.178.0.2/27', defaultRoute='via 172.178.0.1')
        hostB = self.addHost('hostB', ip='172.178.4.2/27', defaultRoute='via 172.178.4.1')
        
        #Membuat objek router 1 sampai router 4
        r1 = self.addNode('r1', cls=LinuxRouter, ip='172.178.2.1/27')
        r2 = self.addNode('r2', cls=LinuxRouter, ip='172.178.3.1/27')
        r3 = self.addNode('r3', cls=LinuxRouter, ip='172.178.2.2/27')
        r4 = self.addNode('r4', cls=LinuxRouter, ip='172.178.3.2/27')
        
        #Untuk memanipulasi buffer dengan ukuran 20, 40, 60 dan 100
        bufSize = 60

        #Menyambungkan router to router
        self.addLink(r1, r3, cls=TCLink, bw=0.5, loss=0, max_queue_size=bufSize, use_tbf=True, 
                     intfName1='r1-eth1', intfName2='r3-eth1', params1={'ip': '172.178.2.1/27'}, params2={'ip': '172.178.2.2/27'})
        self.addLink(r1, r4, cls=TCLink, bw=1, loss=0, max_queue_size=bufSize, use_tbf=True, 
                     intfName1='r1-eth2', intfName2='r4-eth1', params1={'ip': '172.178.6.1/27'}, params2={'ip': '172.178.6.2/27'})
        self.addLink(r2, r4, cls=TCLink, bw=0.5, loss=0, max_queue_size=bufSize, use_tbf=True, 
                     intfName1='r2-eth1', intfName2='r4-eth2', params1={'ip': '172.178.3.1/27'}, params2={'ip': '172.178.3.2/27'})
        self.addLink(r2, r3, cls=TCLink, bw=1, loss=0, max_queue_size=bufSize, use_tbf=True, 
                     intfName1='r2-eth2', intfName2='r3-eth2', params1={'ip': '172.178.7.1/27'}, params2={'ip': '172.178.7.2/27'})

        #Menyambungkan router to host
        self.addLink(hostA, r1, cls=TCLink, bw=1, loss=0, max_queue_size=bufSize, use_tbf=True, 
                     intfName2='r1-eth3', params1={'ip': '172.178.0.2/27'}, params2={'ip': '172.178.0.1/27'})
        self.addLink(hostA, r2, cls=TCLink, bw=1, loss=0, max_queue_size=bufSize, use_tbf=True, 
                     intfName2='r2-eth3', params1={'ip': '172.178.1.2/27'}, params2={'ip': '172.178.1.1/27'})
        self.addLink(hostB, r3, cls=TCLink, bw=1, loss=0, max_queue_size=bufSize, use_tbf=True, 
                     intfName2='r3-eth3', params1={'ip': '172.178.4.2/27'}, params2={'ip': '172.178.4.1/27'})
        self.addLink(hostB, r4, cls=TCLink, bw=1, loss=0, max_queue_size=bufSize, use_tbf=True, 
                     intfName2='r4-eth3', params1={'ip': '172.178.5.2/27'}, params2={'ip': '172.178.5.1/27'})

def run():
    topo = myTopo()
    net = Mininet(topo=topo)
    net.start()
    mulai = datetime.now()

    #Konfigurasi zebra dan ripd 
    for router in net.hosts:
        if router.name[0] == 'r':
            router.cmd(
                "zebra -f config/zebra/{0}zebra.conf -d -i /tmp/{0}zebra.pid > logs/{0}-zebra-stdout 2>&1".format(router.name))
            router.waitOutput()
            router.cmd(
                "ripd -f config/rip/{0}ripd.conf -d -i /tmp/{0}ripd.pid > logs/{0}-ripd-stdout 2>&1".format(router.name), shell=True)
            router.waitOutput()
    
    #Mekanisme static routing MPTCP
    #Untuk host A
    net['hostA'].cmd("ip rule add from 172.178.0.2 table 1")
    net['hostA'].cmd("ip rule add from 172.178.1.2 table 2")
    net['hostA'].cmd("ip route add 172.178.0.0/27 dev hostA-eth0 scope link table 1")
    net['hostA'].cmd("ip route add default via 172.178.0.1 dev hostA-eth0 table 1")
    net['hostA'].cmd("ip route add 172.178.1.0/27 dev hostA-eth1 scope link table 2")
    net['hostA'].cmd("ip route add default via 172.178.1.1 dev hostA-eth1 table 2")
    net['hostA'].cmd("ip route add default scope global nexthop via 172.178.0.1 dev hostA-eth0")
    
    #Untuk host B
    net['hostB'].cmd("ip rule add from 172.178.4.2 table 1")
    net['hostB'].cmd("ip rule add from 172.178.5.2 table 2")
    net['hostB'].cmd("ip route add 172.178.4.0/27 dev hostB-eth0 scope link table 1")
    net['hostB'].cmd("ip route add default via 172.178.4.1 dev hostB-eth0 table 1")
    net['hostB'].cmd("ip route add 172.178.5.0/27 dev hostB-eth1 scope link table 2")
    net['hostB'].cmd("ip route add default via 172.178.5.1 dev hostB-eth1 table 2")
    net['hostB'].cmd("ip route add default scope global nexthop via 172.178.4.1 dev hostB-eth0")

    a = 5
    while (a > 0):
        a = net.pingAll()

    akhir = datetime.now() -  mulai
    print( "Konvergensi Router: " + str(akhir.total_seconds()) + " s")

    CLI(net)
    net.stop()
    os.system("killall -9 zebra ripd")
    os.system("rm -f /tmp/*.log /tmp/*.pid logs/*")

#Main program
if __name__ == '__main__':
    os.system("rm -f /tmp/*.log /tmp/*.pid logs/*")
    os.system("mn -cc")
    os.system("clear")
    setLogLevel('info')
    run()
