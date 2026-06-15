import 'package:flutter/material.dart';

import 'screens/web_screen.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const IkuNaviArApp());
}

class IkuNaviArApp extends StatelessWidget {
  const IkuNaviArApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'IKU NAVI AR',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorSchemeSeed: const Color(0xFF3B82F6),
        useMaterial3: true,
      ),
      home: const WebScreen(),
    );
  }
}
