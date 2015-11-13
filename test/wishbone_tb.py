from litex.gen import *
from litex.soc.interconnect import wishbone
from litex.gen.sim.generic import run_simulation

from litepcie.core import Endpoint
from litepcie.frontend.wishbone import LitePCIeWishboneBridge

from test.common import *
from test.model.host import *

root_id = 0x100
endpoint_id = 0x400


class TB(Module):
    def __init__(self):
        self.submodules.host = Host(64, root_id, endpoint_id,
            phy_debug=False,
            chipset_debug=False,
            host_debug=False)
        self.submodules.endpoint = Endpoint(self.host.phy)

        self.submodules.wishbone_bridge = LitePCIeWishboneBridge(self.endpoint, lambda a: 1)
        self.submodules.sram = wishbone.SRAM(1024, bus=self.wishbone_bridge.wishbone)

    def gen_simulation(self, selfp):
        wr_datas = [seed_to_data(i, True) for i in range(64)]
        for i in range(64):
            yield from self.host.chipset.wr32(i, [wr_datas[i]])

        rd_datas = []
        for i in range(64):
            yield from self.host.chipset.rd32(i)
            rd_datas.append(self.host.chipset.rd32_data[0])

        s, l, e = check(wr_datas, rd_datas)
        print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
    run_simulation(TB(), ncycles=2048, vcd_name="my.vcd", keep_files=True)
