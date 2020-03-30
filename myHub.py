from ryu.base import app_manager
from ryu.ofproto import ofproto_v1_3
from ryu.controller import ofp_event
from ryu.controller.handler import  MAIN_DISPATCHER,CONFIG_DISPATCHER
from ryu.controller.handler  import set_ev_cls

class Hub(app_manager.RyuApp):
    #  kkk
    OFP_VERSION = [ofproto_v1_3.OFP_VERSION]  #from ryu.ofproto

    def __init__(self, *args, **kwargs):
        super(Hub, self).__init__(*args, **kwargs)


    ##处理交换机连接
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def switch_features_handler(self, ev):
        datapath = ev.msg.datapath      #datapath 可以等同于网桥
        ofproto = datapath.ofproto      #openflow版本
        ofp_parser = datapath.ofproto_parser #openflow解析
        
        #安装默认流表项 install the tables-miss flow entry
        match = ofp_parser.OFPMatch()
        actions = [ofp_parser.OFPActionOutput(ofproto.OFPP_CONTROLLER, ofproto.OFPCML_NO_BUFFER)] #controller端口

        self.add_flow(datapath,0,match,actions)

    def add_flow(self, datapath, priority, match, action):
        #add a flow entry, and install it into datapath
        datapath = datapath      #datapath 可以等同于网桥
        ofproto = datapath.ofproto      #openflow版本
        ofp_parser = datapath.ofproto_parser #openflow解析
        inst = [ofp_parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS, actions)]
        mod = ofp_parser.OFPFlowMod(datapath=datapath, priority=priority,match=match,instructions=inst)
        datapath.senf_msg(mod)


    #处理packetin消息
    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)   
    def packet_in_handler(self, ev):
        msg = ev.msg
        datapath = msg.datapath
        ofproto = datapath.ofproto
        ofp_parser = datapath.ofproto_parser
        in_port = msg.match['in_port']
        # 构建一个流表项
        match = ofp_parser.OFPMatch()
        actions = [ofp.ofp_parser.OFPActionOutput(ofproto.OFPP_FLOOD)]
        self.add_flow(datapath,1,match.actions)
        ##构建 packetout
        out = ofp_parser.OFPPacketOut(datapath=datapath,buffer_id=msg.buffer_id,in_port=in_port,actions=actions)
        datapath.send_msg(out)


    

     
