import { useState } from "react";
import { Calendar, Download, Leaf, TrendingUp, Zap, Activity, BarChart3, Waves } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./ui/card";
import { Button } from "./ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs";
import { Badge } from "./ui/badge";
import { AnalyticsChart } from "./AnalyticsChart";
import { RealtimeDataPanel } from "./RealtimeDataPanel";
import { SummaryReportTable } from "./SummaryReportTable";
import { EnvironmentalImpact } from "./EnvironmentalImpact";

interface AnalyticsData {
  deviceId: string;
  timestamp: string;
  kvah: number;
  billing: number;
  kva: number;
  kw: number;
  kwh: number;
  pf: number;
  kvarh_lag: number;
  kvarh_lead: number;
  co2_emissions: number;
}

export function Analytics() {
  const [selectedDevice, setSelectedDevice] = useState("device-001");
  const [selectedShift, setSelectedShift] = useState("all");
  const [selectedGraphType, setSelectedGraphType] = useState("consumption");

  // Mock devices data
  const devices = [
    { id: "device-001", name: "Main Power Panel A", location: "Building A - Floor 1" },
    { id: "device-002", name: "HVAC Control Unit", location: "Building A - Floor 2" },
    { id: "device-003", name: "Manufacturing Line 1", location: "Production Floor" },
    { id: "device-004", name: "Lighting Circuit B", location: "Building B - All Floors" },
    { id: "device-005", name: "Server Room UPS", location: "Data Center" }
  ];

  const shifts = [
    { id: "all", name: "All Shifts" },
    { id: "morning", name: "Morning Shift (6AM - 2PM)" },
    { id: "afternoon", name: "Afternoon Shift (2PM - 10PM)" },
    { id: "night", name: "Night Shift (10PM - 6AM)" }
  ];

  const graphTypes = [
    { id: "consumption", name: "Consumption", icon: TrendingUp },
    { id: "parameterized", name: "Parameterized View", icon: BarChart3 },
    { id: "harmonic", name: "Harmonic Analysis", icon: Waves }
  ];

  // Mock analytics data
  const mockData: AnalyticsData[] = Array.from({ length: 24 }, (_, i) => ({
    deviceId: selectedDevice,
    timestamp: `${String(i).padStart(2, '0')}:00`,
    kvah: 45 + Math.random() * 20,
    billing: (45 + Math.random() * 20) * 8.5, // ₹8.5 per unit
    kva: 42 + Math.random() * 18,
    kw: 38 + Math.random() * 15,
    kwh: 35 + Math.random() * 25,
    pf: 0.85 + Math.random() * 0.1,
    kvarh_lag: 12 + Math.random() * 8,
    kvarh_lead: 8 + Math.random() * 5,
    co2_emissions: (35 + Math.random() * 25) * 0.82 // kg CO2 per kWh
  }));

  const selectedDeviceInfo = devices.find(d => d.id === selectedDevice);

  return (
    <div className="p-6 space-y-6 bg-background min-h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold text-foreground">Analytics</h1>
          <p className="text-muted-foreground mt-1">
            Detailed device-specific energy analysis and insights
          </p>
        </div>
        <Button variant="outline" className="gap-2">
          <Download className="w-4 h-4" />
          Export All Data
        </Button>
      </div>

      {/* Filters Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" />
            Analysis Filters
          </CardTitle>
          <CardDescription>
            Configure your analysis parameters and view settings
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Device Selection */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Device Selection</label>
              <Select value={selectedDevice} onValueChange={setSelectedDevice}>
                <SelectTrigger>
                  <SelectValue placeholder="Select device" />
                </SelectTrigger>
                <SelectContent>
                  {devices.map((device) => (
                    <SelectItem key={device.id} value={device.id}>
                      <div>
                        <div className="font-medium">{device.name}</div>
                        <div className="text-xs text-muted-foreground">{device.location}</div>
                      </div>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Shift Selection */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Shift Filter</label>
              <Select value={selectedShift} onValueChange={setSelectedShift}>
                <SelectTrigger>
                  <SelectValue placeholder="Select shift" />
                </SelectTrigger>
                <SelectContent>
                  {shifts.map((shift) => (
                    <SelectItem key={shift.id} value={shift.id}>
                      {shift.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Graph Type Selection */}
            <div className="space-y-2">
              <label className="text-sm font-medium">Graph Type</label>
              <Select value={selectedGraphType} onValueChange={setSelectedGraphType}>
                <SelectTrigger>
                  <SelectValue placeholder="Select graph type" />
                </SelectTrigger>
                <SelectContent>
                  {graphTypes.map((type) => {
                    const Icon = type.icon;
                    return (
                      <SelectItem key={type.id} value={type.id}>
                        <div className="flex items-center gap-2">
                          <Icon className="w-4 h-4" />
                          {type.name}
                        </div>
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Selected Device Info */}
          {selectedDeviceInfo && (
            <div className="mt-4 p-4 bg-accent/50 rounded-lg">
              <div className="flex items-center gap-3">
                <div className="w-2 h-2 bg-primary rounded-full animate-pulse"></div>
                <div>
                  <h4 className="font-medium">{selectedDeviceInfo.name}</h4>
                  <p className="text-sm text-muted-foreground">{selectedDeviceInfo.location}</p>
                </div>
                <Badge variant="secondary" className="ml-auto">Active</Badge>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Environmental Impact */}
      <EnvironmentalImpact data={mockData} />

      {/* Main Analytics Content */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Charts Section - Takes 2/3 width */}
        <div className="xl:col-span-2 space-y-6">
          <AnalyticsChart 
            data={mockData} 
            graphType={selectedGraphType}
            deviceName={selectedDeviceInfo?.name || "Unknown Device"}
          />
        </div>

        {/* Real-time Data Panel - Takes 1/3 width */}
        <div className="space-y-6">
          <RealtimeDataPanel data={mockData[mockData.length - 1]} />
        </div>
      </div>

      {/* Summary Report Table */}
      <SummaryReportTable 
        data={mockData} 
        deviceName={selectedDeviceInfo?.name || "Unknown Device"}
      />
    </div>
  );
}