class AlarmRecord {
  final String id;
  final String deviceMac;
  final String alarmType;
  final String alarmLevel;
  final String message;
  final String createdAt;
  bool acknowledged;
  final double? anomalyProbability;

  AlarmRecord({
    required this.id,
    required this.deviceMac,
    required this.alarmType,
    required this.alarmLevel,
    required this.message,
    required this.createdAt,
    this.acknowledged = false,
    this.anomalyProbability,
  });

  factory AlarmRecord.fromJson(Map<String, dynamic> json) {
    return AlarmRecord(
      id: json['id'] as String,
      deviceMac: json['device_mac'] as String,
      alarmType: json['alarm_type'] as String,
      alarmLevel: json['alarm_level'] as String? ?? 'info',
      message: json['message'] as String? ?? '',
      createdAt: json['created_at'] as String,
      acknowledged: json['acknowledged'] == true,
      anomalyProbability: (json['anomaly_probability'] as num?)?.toDouble(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'device_mac': deviceMac,
      'alarm_type': alarmType,
      'alarm_level': alarmLevel,
      'message': message,
      'created_at': createdAt,
      'acknowledged': acknowledged,
      'anomaly_probability': anomalyProbability,
    };
  }
}

class AlarmQueueItem {
  final String alarmId;
  final String deviceMac;
  final int priority;
  final String status;

  AlarmQueueItem({
    required this.alarmId,
    required this.deviceMac,
    required this.priority,
    required this.status,
  });

  factory AlarmQueueItem.fromJson(Map<String, dynamic> json) {
    return AlarmQueueItem(
      alarmId: json['alarm_id'] as String,
      deviceMac: json['device_mac'] as String,
      priority: json['priority'] as int? ?? 0,
      status: json['status'] as String? ?? 'pending',
    );
  }
}

class MobilePushRecord {
  final String id;
  final String title;
  final String body;
  final String createdAt;

  MobilePushRecord({
    required this.id,
    required this.title,
    required this.body,
    required this.createdAt,
  });

  factory MobilePushRecord.fromJson(Map<String, dynamic> json) {
    return MobilePushRecord(
      id: json['id'] as String,
      title: json['title'] as String,
      body: json['body'] as String,
      createdAt: json['created_at'] as String,
    );
  }
}
