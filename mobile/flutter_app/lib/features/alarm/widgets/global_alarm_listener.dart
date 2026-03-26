import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/alarm_provider.dart';

class GlobalAlarmListener extends StatefulWidget {
  final Widget child;

  const GlobalAlarmListener({super.key, required this.child});

  @override
  State<GlobalAlarmListener> createState() => _GlobalAlarmListenerState();
}

class _GlobalAlarmListenerState extends State<GlobalAlarmListener> {
  final Set<String> _shownAlarmIds = {};

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AlarmProvider>().addListener(_onAlarmChange);
    });
  }

  @override
  void dispose() {
    context.read<AlarmProvider>().removeListener(_onAlarmChange);
    super.dispose();
  }

  void _onAlarmChange() {
    final provider = context.read<AlarmProvider>();
    for (var alarm in provider.alarms) {
      if (!alarm.acknowledged && 
          (alarm.alarmType == 'sos' || alarm.alarmLevel == 'high') && 
          !_shownAlarmIds.contains(alarm.id)) {
        
        _shownAlarmIds.add(alarm.id);
        _showSosAlert(alarm);
      }
    }
  }

  void _showSosAlert(dynamic alarm) {
    if (!mounted) return;
    
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) {
        return AlertDialog(
          backgroundColor: const Color(0xFF1A0A0A),
          shape: RoundedRectangleBorder(
            side: const BorderSide(color: Colors.redAccent, width: 2),
            borderRadius: BorderRadius.circular(16),
          ),
          title: const Row(
            children: [
              Icon(Icons.warning, color: Colors.redAccent, size: 28),
              SizedBox(width: 12),
              Text('紧急求助报警', style: TextStyle(color: Colors.redAccent, fontWeight: FontWeight.bold)),
            ],
          ),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (alarm.deviceMac.isNotEmpty) ...[
                Text('设备 MAC: ${alarm.deviceMac}', style: const TextStyle(color: Colors.white, fontSize: 16)),
                const SizedBox(height: 8),
              ],
              Text('时间: ${alarm.createdAt.toString().split('.')[0]}', style: const TextStyle(color: Colors.white70)),
              const SizedBox(height: 12),
              const Text('老人可能遇到紧急情况，请立即联系或前往处理！', style: TextStyle(color: Colors.white)),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () {
                context.read<AlarmProvider>().acknowledge(alarm.id);
                Navigator.pop(context);
              },
              child: const Text('我知道了', style: TextStyle(color: Colors.redAccent, fontWeight: FontWeight.bold, fontSize: 16)),
            ),
          ],
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return widget.child;
  }
}
