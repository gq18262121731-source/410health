class TrendPoint {
  final DateTime timestamp;
  final double value;

  TrendPoint({required this.timestamp, required this.value});

  factory TrendPoint.fromJson(Map<String, dynamic> json) {
    return TrendPoint(
      timestamp: DateTime.parse(json['timestamp'] as String),
      value: (json['value'] as num).toDouble(),
    );
  }
}

class HistoryBucket {
  final String bucketStart;
  final String bucketEnd;
  final double? heartRate;
  final double? temperature;
  final double? bloodOxygen;
  final int? healthScore;
  final int steps;
  final int sosCount;

  HistoryBucket({
    required this.bucketStart,
    required this.bucketEnd,
    this.heartRate,
    this.temperature,
    this.bloodOxygen,
    this.healthScore,
    required this.steps,
    required this.sosCount,
  });

  factory HistoryBucket.fromJson(Map<String, dynamic> json) {
    return HistoryBucket(
      bucketStart: json['bucket_start'] as String,
      bucketEnd: json['bucket_end'] as String,
      heartRate: (json['heart_rate'] as num?)?.toDouble(),
      temperature: (json['temperature'] as num?)?.toDouble(),
      bloodOxygen: (json['blood_oxygen'] as num?)?.toDouble(),
      healthScore: json['health_score'] as int?,
      steps: json['steps'] as int? ?? 0,
      sosCount: json['sos_count'] as int? ?? 0,
    );
  }
}

class DeviceHistoryResponse {
  final String window;
  final List<HistoryBucket> points;

  DeviceHistoryResponse({required this.window, required this.points});

  factory DeviceHistoryResponse.fromJson(Map<String, dynamic> json) {
    return DeviceHistoryResponse(
      window: json['window'] as String,
      points: (json['points'] as List)
          .map((e) => HistoryBucket.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}
