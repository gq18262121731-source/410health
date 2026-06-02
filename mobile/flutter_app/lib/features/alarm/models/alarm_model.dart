class AlarmRecord {
  final String id;
  final String deviceMac;
  final String alarmType;
  final String alarmLevel;
  final int? alarmPriority;
  final String message;
  final String createdAt;
  bool acknowledged;
  final double? anomalyProbability;
  final Map<String, dynamic> metadata;

  AlarmRecord({
    required this.id,
    required this.deviceMac,
    required this.alarmType,
    required this.alarmLevel,
    this.alarmPriority,
    required this.message,
    required this.createdAt,
    this.acknowledged = false,
    this.anomalyProbability,
    this.metadata = const {},
  });

  factory AlarmRecord.fromJson(Map<String, dynamic> json) {
    final rawLevel = json['alarm_level'];
    return AlarmRecord(
      id: json['id'] as String,
      deviceMac: json['device_mac'] as String,
      alarmType: json['alarm_type'] as String,
      alarmLevel: _normalizeAlarmLevel(rawLevel),
      alarmPriority: _parseAlarmPriority(rawLevel),
      message: json['message'] as String? ?? '',
      createdAt: json['created_at'] as String,
      acknowledged: json['acknowledged'] == true,
      anomalyProbability: (json['anomaly_probability'] as num?)?.toDouble(),
      metadata: _parseMetadata(json['metadata']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'device_mac': deviceMac,
      'alarm_type': alarmType,
      'alarm_level': alarmPriority ?? alarmLevel,
      'message': message,
      'created_at': createdAt,
      'acknowledged': acknowledged,
      'anomaly_probability': anomalyProbability,
      'metadata': metadata,
    };
  }

  bool get isSos => alarmType.toLowerCase() == 'sos';

  bool get isFall {
    final normalized = alarmType.toLowerCase();
    return normalized == 'fall_detected' || normalized == 'fall_injury_risk';
  }

  bool get isCritical =>
      alarmLevel == 'sos' ||
      alarmLevel == 'critical' ||
      ((alarmPriority ?? 99) <= 2);

  DateTime? get createdAtDateTime {
    final parsed = DateTime.tryParse(createdAt);
    return parsed?.toLocal();
  }

  String get createdAtDisplay {
    final parsed = createdAtDateTime;
    if (parsed == null) {
      return createdAt;
    }
    return _formatDateTime(parsed);
  }

  String get createdDateDisplay {
    final parsed = createdAtDateTime;
    if (parsed == null) {
      return createdAt.split('T').first;
    }
    return _formatDate(parsed);
  }

  String? get elderName => _readNonEmptyString(metadata['elder_name']);

  String? get deviceName => _readNonEmptyString(metadata['device_name']);

  String? get apartment => _readNonEmptyString(metadata['apartment']);

  String? get sosTrigger => _readNonEmptyString(metadata['sos_trigger']);

  String? get incidentId => _readNonEmptyString(
        metadata['incident_id'] ??
            (_fallEvent != null
                ? _fallEvent!['incident_id']
                : null),
      );

  Map<String, dynamic>? get fallPresentation => _asMap(metadata['presentation']);

  Map<String, dynamic>? get familyGuidance => _asMap(metadata['family_guidance']);

  Map<String, dynamic>? get _fallEvent => _asMap(metadata['event']);

  String get fallSeverityLabel {
    final guidance = familyGuidance;
    final presentation = fallPresentation;
    final fromGuidance = _readNonEmptyString(guidance?['severity_label']);
    if (fromGuidance != null) return fromGuidance;
    final state = _readNonEmptyString(presentation?['event_state']) ??
        _readNonEmptyString(_fallEvent?['state']) ??
        '';
    final injury = _readNonEmptyString(metadata['injury_level']) ??
        _readNonEmptyString(_asMap(_fallEvent?['injury'])?['level']) ??
        '';
    if (state == 'abnormal_recovery' ||
        state == 'emergency' ||
        state == 'needs_assistance' ||
        injury == 'I3' ||
        injury == 'I4' ||
        injury == 'I5' ||
        alarmLevel == 'critical') {
      return '高危跌倒';
    }
    if (state == 'confirmed_fall') return '已确认跌倒';
    if (state == 'post_fall_monitoring' || state == 'injury_watch') {
      return '跌倒后持续观察';
    }
    if (state == 'suspected_fall' || state == 'possible_fall') {
      return '疑似跌倒';
    }
    return '跌倒风险提醒';
  }

  String get fallTitle {
    final presentation = fallPresentation;
    return _readNonEmptyString(presentation?['title']) ??
        (isFall ? fallSeverityLabel : headlineDisplay);
  }

  String? get fallLead => _readNonEmptyString(fallPresentation?['lead']);

  String? get familyMessage =>
      _readNonEmptyString(familyGuidance?['family_message']);

  String? get fallSnapshotUrl =>
      _readNonEmptyString(_fallEvent?['snapshot_url']) ??
      _readNonEmptyString(_fallEvent?['snapshot_path']);

  bool get shouldCallEmergency => familyGuidance?['call_emergency'] == true;

  List<String> get recommendedActions {
    final guidanceActions = _asStringList(familyGuidance?['immediate_actions']);
    if (guidanceActions.isNotEmpty) return guidanceActions;
    final presentationActions =
        _asStringList(fallPresentation?['recommended_actions']);
    return presentationActions;
  }

  List<String> get contraindications =>
      _asStringList(familyGuidance?['contraindications']);

  String get reviewStatus =>
      _readNonEmptyString(fallPresentation?['review_status']) ??
      'not_required';

  bool get showImmediatePopup => fallPresentation?['show_immediate_popup'] == true;

  String get sosTriggerLabel {
    switch (sosTrigger) {
      case 'long_press':
        return '长按手环按钮';
      case 'double_click':
        return '双击手环按钮';
      default:
        return '紧急求助';
    }
  }

  String get headlineDisplay {
    if (elderName != null && apartment != null) {
      return '$elderName / $apartment';
    }
    if (elderName != null) {
      return elderName!;
    }
    if (deviceName != null) {
      return deviceName!;
    }
    return deviceMac;
  }

  String get detailDisplay {
    final parts = <String>[];
    if (deviceName != null) {
      parts.add(deviceName!);
    }
    parts.add(sosTriggerLabel);
    return parts.join(' · ');
  }

  static int? _parseAlarmPriority(dynamic rawLevel) {
    if (rawLevel is num) {
      return rawLevel.toInt();
    }
    if (rawLevel is String) {
      return int.tryParse(rawLevel);
    }
    return null;
  }

  static Map<String, dynamic> _parseMetadata(dynamic rawMetadata) {
    if (rawMetadata is Map) {
      return Map<String, dynamic>.from(rawMetadata);
    }
    return const {};
  }

  static Map<String, dynamic>? _asMap(dynamic raw) {
    if (raw is Map) {
      return Map<String, dynamic>.from(raw);
    }
    return null;
  }

  static List<String> _asStringList(dynamic raw) {
    if (raw is! List) {
      return const <String>[];
    }
    return raw
        .map((item) => item?.toString().trim() ?? '')
        .where((item) => item.isNotEmpty)
        .toList(growable: false);
  }

  static String? _readNonEmptyString(dynamic rawValue) {
    if (rawValue is! String) {
      return null;
    }
    final normalized = rawValue.trim();
    return normalized.isEmpty ? null : normalized;
  }

  static String _normalizeAlarmLevel(dynamic rawLevel) {
    if (rawLevel is num) {
      return _levelFromPriority(rawLevel.toInt());
    }
    if (rawLevel is String) {
      final numeric = int.tryParse(rawLevel);
      if (numeric != null) {
        return _levelFromPriority(numeric);
      }
      return rawLevel.toLowerCase();
    }
    return 'info';
  }

  static String _levelFromPriority(int priority) {
    switch (priority) {
      case 1:
        return 'sos';
      case 2:
        return 'critical';
      case 3:
        return 'warning';
      default:
        return 'info';
    }
  }

  static String _formatDateTime(DateTime value) {
    return '${_formatDate(value)} ${_twoDigits(value.hour)}:${_twoDigits(value.minute)}:${_twoDigits(value.second)}';
  }

  static String _formatDate(DateTime value) {
    return '${value.year}-${_twoDigits(value.month)}-${_twoDigits(value.day)}';
  }

  static String _twoDigits(int value) {
    return value.toString().padLeft(2, '0');
  }
}

class AlarmQueueItem {
  final double score;
  final AlarmRecord alarm;

  AlarmQueueItem({
    required this.score,
    required this.alarm,
  });

  factory AlarmQueueItem.fromJson(Map<String, dynamic> json) {
    return AlarmQueueItem(
      score: (json['score'] as num?)?.toDouble() ?? 0.0,
      alarm: AlarmRecord.fromJson(json['alarm'] as Map<String, dynamic>),
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
