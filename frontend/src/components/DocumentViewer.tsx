import React from 'react';

interface DocumentViewerProps {
  docId?: string | null;
}

const DocumentViewer: React.FC<DocumentViewerProps> = ({ docId }) => {
  return (
    <div className="flex-1 overflow-y-auto p-8 flex justify-center bg-[#525659]">
      <div className="bg-white w-full max-w-[800px] min-h-[1100px] shadow-2xl relative">
        <div className="p-12 pb-4">
          <div className="flex justify-between items-end border-b-2 border-black pb-2 mb-8">
            <h1 className="text-3xl font-bold font-serif text-black">Datasheet MCU-V2</h1>
            <span className="text-sm font-mono">Rev 2.1 - 2023</span>
          </div>

          <h2 className="text-xl font-bold mb-4 text-black">3. Pin Configuration</h2>
          <p className="text-sm text-gray-700 mb-6 text-justify leading-relaxed">
            The MCU-V2 series provides a comprehensive set of peripherals. The pin assignment is designed to minimize trace length for high-speed signals. Refer to Table 3-1 for detailed pin descriptions.
          </p>

          <div className="w-full aspect-[2/1] bg-slate-50 border border-slate-200 mb-8 relative flex items-center justify-center overflow-hidden rounded">
            <div className="absolute inset-0 opacity-10" style={{ backgroundImage: 'radial-gradient(#000 1px, transparent 1px)', backgroundSize: '20px 20px' }} />
            <div className="w-64 h-48 border-2 border-slate-800 bg-white relative shadow-sm">
              <div className="absolute inset-0 flex items-center justify-center font-mono font-bold text-slate-300 text-4xl select-none">MCU</div>
            </div>
          </div>

          <h3 className="font-bold text-sm mb-2 text-black">Table 3-1. Pin Descriptions</h3>
          <div className="w-full border border-black text-xs font-mono">
            <div className="grid grid-cols-4 bg-gray-200 border-b border-black font-bold">
              <div className="p-2 border-r border-black">Pin No.</div>
              <div className="p-2 border-r border-black">Name</div>
              <div className="p-2 border-r border-black">Type</div>
              <div className="p-2">Function</div>
            </div>
            <div className="grid grid-cols-4 border-b border-gray-300">
              <div className="p-2 border-r border-gray-300">1</div>
              <div className="p-2 border-r border-gray-300">VDD</div>
              <div className="p-2 border-r border-gray-300">Power</div>
              <div className="p-2">Main Power Supply</div>
            </div>
            <div className="grid grid-cols-4 border-b border-gray-300 bg-gray-50">
              <div className="p-2 border-r border-gray-300">2</div>
              <div className="p-2 border-r border-gray-300">GND</div>
              <div className="p-2 border-r border-gray-300">Power</div>
              <div className="p-2">Ground</div>
            </div>
            <div className="grid grid-cols-4 border-b border-gray-300">
              <div className="p-2 border-r border-gray-300">3</div>
              <div className="p-2 border-r border-gray-300">GPIO_0</div>
              <div className="p-2 border-r border-gray-300">I/O</div>
              <div className="p-2">General Purpose I/O</div>
            </div>
            <div className="grid grid-cols-4 border-b border-gray-300 bg-gray-50">
              <div className="p-2 border-r border-gray-300">...</div>
              <div className="p-2 border-r border-gray-300">...</div>
              <div className="p-2 border-r border-gray-300">...</div>
              <div className="p-2">...</div>
            </div>
            <div className="grid grid-cols-4 border-b border-gray-300">
              <div className="p-2 border-r border-gray-300">48</div>
              <div className="p-2 border-r border-gray-300">RESET</div>
              <div className="p-2 border-r border-gray-300">Input</div>
              <div className="p-2">System Reset</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DocumentViewer;
