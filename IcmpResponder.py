# -*- coding: utf-8 -*-

from ryu.lib.packet import *
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
class IcmpResponder(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]
    def __init__(self, *args, **kwargs):
        super(IcmpResponder, self).__init__(*args, **kwargs)
        self.hw_addr = '66:66:66:66:66:66'       #初始化,这里预先定义了一个MAC地址用来响应主机的数据包

    # 下发默认流表
    # 在交换机和控制器建立连接之后，因为在这里交换机还无法响应主机的数据包，
    # 所以给交换机下发一个Table-miss流表项，告诉交换机以后收到的数据包都交给控制器处理。
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def _switch_features_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        actions = [parser.OFPActionOutput(port=ofproto.OFPP_CONTROLLER,max_len=ofproto.OFPCML_NO_BUFFER)] 
        # OFPCML_NO_BUFFER,这里指示交换机不缓存数据包，把数据包封装一下发给控制器。

        inst = [parser.OFPInstructionActions(type_=ofproto.OFPIT_APPLY_ACTIONS,actions=actions)]

        # 函数OFPFlowMod专门用于下发流表，其中流表的优先级priority设置为0，意为最后匹配；匹配域OFPMatch()是空的，表示匹配所有。
        mod = parser.OFPFlowMod(datapath=datapath,priority=0,match=parser.OFPMatch(),instructions=inst)

        datapath.send_msg(mod)

    # 处理packet-in消息
    # 主机发出数据包，交换机读取之后发现不知道向哪里发送，这时候由于Table-miss的存在，
    # 它会向控制器转发这个数据包，控制器将这个数据包解析，进行回应。
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def _packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        port = msg.match['in_port']
        pkt = packet.Packet(data=msg.data)
        self.logger.info("--------------------")
        self.logger.info("Receive Packet-in from %d",datapath.id)
        pkt_ethernet = pkt.get_protocol(ethernet.ethernet)
        if not pkt_ethernet:
            return
        pkt_arp = pkt.get_protocol(arp.arp)
        if pkt_arp:
            self._handle_arp(datapath, port, pkt_ethernet, pkt_arp)
            return
        pkt_ipv4 = pkt.get_protocol(ipv4.ipv4)
    
        pkt_icmp = pkt.get_protocol(icmp.icmp)
        if pkt_icmp:
            self._handle_icmp(datapath, port, pkt_ethernet, pkt_ipv4, pkt_icmp)
            return

    def _handle_arp(self, datapath, port, pkt_ethernet, pkt_arp):
        if pkt_arp.opcode != arp.ARP_REQUEST:
            return
        pkt = packet.Packet()  # 因为我们的处理是回复这个请求，所以我们要构造一个数据包发回去，首先我们生成一个数据包对象

        # 然后向里面逐层添加协议，把一些必要的参数设置好
        # 以太网类型是默认的，目的MAC地址是源数据包的源MAC地址，源MAC地址是我们预先定义的MAC地址
        # ARP消息的类型是REPLY，源IP地址是源数据包请求的，目的IP是源数据包的源IP地址
        pkt.add_protocol(ethernet.ethernet(ethertype=pkt_ethernet.ethertype,dst=pkt_ethernet.src,src=self.hw_addr))
        pkt.add_protocol(arp.arp(opcode=arp.ARP_REPLY,src_mac=self.hw_addr,src_ip=pkt_arp.dst_ip,dst_mac=pkt_arp.src_mac,dst_ip=pkt_arp.src_ip))
        
        self.logger.info("Receive ARP_REQUEST,request IP is %s",pkt_arp.dst_ip)
        self._send_packet(datapath, port, pkt)

    def _handle_icmp(self, datapath, port, pkt_ethernet, pkt_ipv4, pkt_icmp):
        if pkt_icmp.type != icmp.ICMP_ECHO_REQUEST:
            return
        pkt = packet.Packet()
        pkt.add_protocol(ethernet.ethernet(ethertype=pkt_ethernet.ethertype,dst=pkt_ethernet.src,src=self.hw_addr))
        pkt.add_protocol(ipv4.ipv4(dst=pkt_ipv4.src,src=pkt_ipv4.dst,proto=pkt_ipv4.proto))
        pkt.add_protocol(icmp.icmp(type_=icmp.ICMP_ECHO_REPLY,code=icmp.ICMP_ECHO_REPLY_CODE,csum=0,data=pkt_icmp.data))
        self.logger.info("Receive ICMP_ECHO_REQUEST,request IP is %s",pkt_ipv4.dst)
        self._send_packet(datapath, port, pkt)

    def _send_packet(self, datapath, port, pkt):
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser
        pkt.serialize()
        if pkt.get_protocol(icmp.icmp):
            self.logger.info("Send ICMP_ECHO_REPLY")
        if  pkt.get_protocol(arp.arp):
            self.logger.info("Send ARP_REPLY")
        self.logger.info("--------------------")
        data = pkt.data
        actions = [parser.OFPActionOutput(port=port)]
        # 构造一个Packet-Out数据包发送到交换机，之前没有缓存数据包，这里也要指明不是缓存的数据包
        out = parser.OFPPacketOut(datapath=datapath,buffer_id=ofproto.OFP_NO_BUFFER,in_port=ofproto.OFPP_CONTROLLER,actions=actions,data=data)
        datapath.send_msg(out)
