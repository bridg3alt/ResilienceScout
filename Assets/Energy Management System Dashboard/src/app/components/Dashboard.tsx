import { useState } from "react";
import { Badge } from "./ui/badge";
import { ConsumptionChart } from "./ConsumptionChart";
import { DemandChart } from "./DemandChart";
import { EnergyParameters } from "./EnergyParameters";
import { EnhancedFilterSection } from "./EnhancedFilterSection";

export function Dashboard() {
  const [selectedFilterType, setSelectedFilterType] = useState<"device" | "virtual-group">("device");
  const [selectedDevice, setSelectedDevice] = useState("device-1");
  const [selectedDevices, setSelectedDevices] = useState<string[]>([]);
  const [dataMode, setDataMode] = useState("real-time");
  const [selectedDay, setSelectedDay] = useState("today");

  const handleApplyFilters = () => {
    // In a real application, this would trigger data fetching
    console.log("Applying filters:", {
      filterType: selectedFilterType,
      device: selectedDevice,
      devices: selectedDevices,
      dataMode,
      selectedDay,
    });
  };

  const handleFilterTypeChange = (type: "device" | "virtual-group") => {
    setSelectedFilterType(type);
    if (type === "device") {
      setSelectedDevice("device-1");
      setSelectedDevices([]);
    } else {
      setSelectedDevice("group-production");
      setSelectedDevices([]);
    }
  };

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#f8faf9' }}>
      <div className="p-6 space-y-6">
        {/* Header Section */}
        <div className="flex flex-col space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-semibold text-foreground">Hello, Liam Gallagher! 👋</h1>
              <p className="text-muted-foreground mt-1">
                What are you looking for today?
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge className="bg-primary/10 text-primary border-primary/20 px-3 py-1.5">
                <div className="w-2 h-2 bg-primary rounded-full mr-2 animate-pulse"></div>
                Real-time monitoring active
              </Badge>
            </div>
          </div>
        </div>

        {/* Enhanced Filter Section */}
        <EnhancedFilterSection
          selectedFilterType={selectedFilterType}
          selectedDevice={selectedDevice}
          selectedDevices={selectedDevices}
          dataMode={dataMode}
          selectedDay={selectedDay}
          onFilterTypeChange={handleFilterTypeChange}
          onDeviceChange={setSelectedDevice}
          onDevicesChange={setSelectedDevices}
          onDataModeChange={setDataMode}
          onDayChange={setSelectedDay}
          onApplyFilters={handleApplyFilters}
        />

        {/* Energy Parameters */}
        <EnergyParameters 
          dataMode={dataMode} 
          selectedDevice={selectedFilterType === "device" ? selectedDevice : selectedDevices.join(",")} 
        />

        {/* Charts Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Consumption Overview */}
          <ConsumptionChart 
            selectedDay={selectedDay} 
            selectedDevice={selectedFilterType === "device" ? selectedDevice : selectedDevices.join(",")} 
          />
          
          {/* Max vs Actual Demand */}
          <DemandChart dataMode={dataMode} selectedDay={selectedDay} />
        </div>
      </div>
    </div>
  );
}