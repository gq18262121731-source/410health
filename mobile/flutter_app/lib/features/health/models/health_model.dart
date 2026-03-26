class HealthData {
  final String deviceMac;
  final DateTime timestamp;
  final double? heartRate;
  final double? temperature;
  final double? bloodOxygen;
  final String? bloodPressure;
  final int? battery;
  final bool sosFlag;
  final int? steps;
  final int? healthScore;

  HealthData({
    required this.deviceMac,
    required this.timestamp,
    this.heartRate,
    this.temperature,
    this.bloodOxygen,
    this.bloodPressure,
    this.battery,
    this.sosFlag = false,
    this.steps,
    this.healthScore,
  });

  factory HealthData.fromJson(Map<String, dynamic> json) {
    return HealthData(
      deviceMac: json['device_mac'] as String? ?? '',
      timestamp: json['timestamp'] != null 
          ? DateTime.parse(json['timestamp'] as String) 
          : DateTime.now(),
      heartRate: (json['heart_rate'] as num?)?.toDouble(),
      temperature: (json['temperature'] as num?)?.toDouble(),
      bloodOxygen: (json['blood_oxygen'] as num?)?.toDouble(),
      bloodPressure: json['blood_pressure'] as String?,
      battery: json['battery'] as int?,
      sosFlag: json['sos_flag'] == true || (json['sos_value'] as num? ?? 0) > 0,
      steps: json['steps'] as int?,
      healthScore: json['health_score'] as int?,
    );
  }

  // 用于合并 WebSocket 增量数据
  HealthData copyWith({
    double? heartRate,
    double? temperature,
    double? bloodOxygen,
    String? bloodPressure,
    int? battery,
    bool? sosFlag,
    int? steps,
    int? healthScore,
  }) {
    return HealthData(
      deviceMac: deviceMac,
      timestamp: DateTime.now(),
      heartRate: heartRate ?? this.heartRate,
      temperature: temperature ?? this.temperature,
      bloodOxygen: bloodOxygen ?? this.bloodOxygen,
      bloodPressure: bloodPressure ?? this.bloodPressure,
      battery: battery ?? this.battery,
      sosFlag: sosFlag ?? this.sosFlag,
      steps: steps ?? this.steps,
      healthScore: healthScore ?? this.healthScore,
    );
  }
}
