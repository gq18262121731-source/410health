import 'package:flutter/material.dart';

import 'screens/dashboard_screen.dart';
import 'screens/role_selector_screen.dart';

void main() {
  runApp(const AiHealthApp());
}

class AiHealthApp extends StatefulWidget {
  const AiHealthApp({super.key});

  @override
  State<AiHealthApp> createState() => _AiHealthAppState();
}

class _AiHealthAppState extends State<AiHealthApp> {
  String? _role;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'AIoT Health IoT',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFFFF875A)),
        useMaterial3: true,
      ),
      home: _role == null
          ? RoleSelectorScreen(onSelect: (role) => setState(() => _role = role))
          : DashboardScreen(role: _role!),
    );
  }
}
