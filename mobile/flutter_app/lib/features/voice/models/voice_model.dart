class VoiceStatus {
  final bool configured;
  final String? serviceProvider;
  final List<String> supportedLanguages;

  VoiceStatus({
    required this.configured,
    this.serviceProvider,
    required this.supportedLanguages,
  });

  factory VoiceStatus.fromJson(Map<String, dynamic> json) {
    return VoiceStatus(
      configured: json['configured'] as bool? ?? false,
      serviceProvider: json['service_provider'] as String?,
      supportedLanguages: (json['supported_languages'] as List? ?? []).cast<String>(),
    );
  }
}

class AsrResponse {
  final String text;
  final double confidence;

  AsrResponse({required this.text, required this.confidence});

  factory AsrResponse.fromJson(Map<String, dynamic> json) {
    return AsrResponse(
      text: json['text'] as String? ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
    );
  }
}

class TtsResponse {
  final String audioUrl;

  TtsResponse({required this.audioUrl});

  factory TtsResponse.fromJson(Map<String, dynamic> json) {
    return TtsResponse(
      audioUrl: json['audio_url'] as String? ?? '',
    );
  }
}
