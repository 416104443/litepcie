from litex.gen import *

from litex.soc.interconnect.csr import *

from litepcie.common import *
from litepcie.frontend.dma.common import *
from litepcie.frontend.dma.writer import DMAWriter
from litepcie.frontend.dma.reader import DMAReader


class DMALoopback(Module, AutoCSR):
    def __init__(self, data_width):
        self._enable = CSRStorage()

        self.sink = Sink(dma_layout(data_width))
        self.source = Source(dma_layout(data_width))

        self.next_source = Source(dma_layout(data_width))
        self.next_sink = Sink(dma_layout(data_width))

        # # #

        enable = self._enable.storage
        self.comb += \
                If(enable,
                    Record.connect(self.sink, self.source)
                ).Else(
                    Record.connect(self.sink, self.next_source),
                    Record.connect(self.next_sink, self.source)
                )


class DMASynchronizer(Module, AutoCSR):
    def __init__(self, data_width):
        self._bypass = CSRStorage()
        self._enable = CSRStorage()
        self.ready = Signal(reset=1)
        self.pps = Signal()

        self.sink = Sink(dma_layout(data_width))
        self.source = Source(dma_layout(data_width))

        self.next_source = Source(dma_layout(data_width))
        self.next_sink = Sink(dma_layout(data_width))

        # # #

        bypass = self._bypass.storage
        enable = self._enable.storage
        synced = Signal()

        self.sync += \
            If(~enable,
                synced.eq(0)
            ).Else(
                If(self.ready & self.sink.stb & (self.pps | bypass),
                    synced.eq(1)
                )
            )

        self.comb += \
            If(synced,
                Record.connect(self.sink, self.next_source),
                Record.connect(self.next_sink, self.source),
            ).Else(
                # Block sink
                self.next_source.stb.eq(0),
                self.sink.ack.eq(0),

                # Ack next_sink
                self.source.stb.eq(0),
                self.next_sink.ack.eq(1),
            )


class DMABuffering(Module, AutoCSR):
    def __init__(self, data_width, depth):
        tx_fifo = SyncFIFO(dma_layout(data_width), depth//(data_width//8), buffered=True)
        rx_fifo = SyncFIFO(dma_layout(data_width), depth//(data_width//8), buffered=True)
        self.submodules += tx_fifo, rx_fifo

        self.sink = tx_fifo.sink
        self.source = rx_fifo.source

        self.next_source = tx_fifo.source
        self.next_sink = rx_fifo.sink


class DMA(Module, AutoCSR):
    def __init__(self, phy, endpoint,
        with_buffering=False, buffering_depth=256*8,
        with_loopback=False,
        with_synchronizer=False):

        # Writer, Reader
        self.submodules.writer = DMAWriter(endpoint, endpoint.crossbar.get_master_port(write_only=True))
        self.submodules.reader = DMAReader(endpoint, endpoint.crossbar.get_master_port(read_only=True))
        self.sink, self.source = self.writer.sink, self.reader.source

        # Loopback
        if with_loopback:
            self.submodules.loopback = DMALoopback(phy.data_width)
            self.insert_optional_module(self.loopback)

        # Synchronizer
        if with_synchronizer:
            self.submodules.synchronizer = DMASynchronizer(phy.data_width)
            self.insert_optional_module(self.synchronizer)

        # Buffering
        if with_buffering:
            self.submodules.buffering = DMABuffering(phy.data_width, buffering_depth)
            self.insert_optional_module(self.buffering)


    def insert_optional_module(self, m):
        self.comb += [
            Record.connect(self.source, m.sink),
            Record.connect(m.source, self.sink)
        ]
        self.sink, self.source = m.next_sink, m.next_source
