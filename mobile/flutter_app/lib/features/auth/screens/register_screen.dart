import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../models/register_models.dart';
import '../providers/auth_provider.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  RegisterRole _selectedRole = RegisterRole.family;
  int _step = 0; // 0=ËßíËâ≤ÈÄâÊã©, 1=Â°´ÂÜô‰ø°ÊÅØ

  final _nameCtrl = TextEditingController();
  final _phoneCtrl = TextEditingController();
  final _passwordCtrl = TextEditingController();
  final _loginUsernameCtrl = TextEditingController();
  final _ageCtrl = TextEditingController(text: '78');
  final _apartmentCtrl = TextEditingController();

  String _relationship = 'daughter';
  bool _obscurePassword = true;

  static const _relationships = [
    ('daughter', 'Â•≥ÂÑø'),
    ('son', 'ÂÑøÂ≠ê'),
    ('spouse', 'ÈÖçÂÅ∂'),
    ('granddaughter', 'Â≠ôÂ•≥'),
    ('grandson', 'Â≠ôÂ≠ê'),
    ('relative', '‰∫≤Â±û'),
  ];

  @override
  void dispose() {
    _nameCtrl.dispose();
    _phoneCtrl.dispose();
    _passwordCtrl.dispose();
    _loginUsernameCtrl.dispose();
    _ageCtrl.dispose();
    _apartmentCtrl.dispose();
    super.dispose();
  }

  String? _validate() {
    if (_nameCtrl.text.trim().isEmpty) return 'ËØ∑ËæìÂÖ•ÂßìÂêç';
    if (_selectedRole == RegisterRole.elder) {
      if (_phoneCtrl.text.trim().isEmpty) return 'ËØ∑ËæìÂÖ•ÊâãÊú∫Âè∑Ôºà‰Ωú‰∏∫ÁôªÂΩïË¥¶Âè∑Ôºâ';
      final age = int.tryParse(_ageCtrl.text.trim());
      if (age == null || age < 50 || age > 120) return 'ËØ∑ËæìÂÖ•ÊúâÊïàÂπ¥ÈæÑÔºà50-120Ôºâ';
      if (_apartmentCtrl.text.trim().isEmpty) return 'ËØ∑ËæìÂÖ•ÊàøÈó¥Âè∑';
    } else {
      if (_phoneCtrl.text.trim().isEmpty) return 'ËØ∑ËæìÂÖ•ÊâãÊú∫Âè∑';
    }
    if (_passwordCtrl.text.length < 6) return 'ÂØÜÁ†ÅËá≥Â∞ë 6 ‰Ωç';
    return null;
  }

  Future<void> _submit() async {
    final error = _validate();
    if (error != null) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(error), backgroundColor: Colors.redAccent),
      );
      return;
    }

    final provider = context.read<AuthProvider>();
    provider.resetRegisterState();

    final name = _nameCtrl.text.trim();
    final phone = _phoneCtrl.text.trim();
    final password = _passwordCtrl.text;
    final loginUsername = _loginUsernameCtrl.text.trim();

    bool ok = false;
    if (_selectedRole == RegisterRole.elder) {
      ok = await provider.registerElder(ElderRegisterRequest(
        name: name,
        phone: phone,
        password: password,
        age: int.tryParse(_ageCtrl.text.trim()) ?? 78,
        apartment: _apartmentCtrl.text.trim(),
      ));
    } else if (_selectedRole == RegisterRole.family) {
      ok = await provider.registerFamily(FamilyRegisterRequest(
        name: name,
        phone: phone,
        password: password,
        relationship: _relationship,
        loginUsername: loginUsername.isEmpty ? null : loginUsername,
      ));
    } else {
      ok = await provider.registerCommunity(CommunityRegisterRequest(
        name: name,
        phone: phone,
        password: password,
        loginUsername: loginUsername.isEmpty ? null : loginUsername,
      ));
    }

    if (!mounted) return;
    if (ok) _showSuccessDialog();
  }

  void _showSuccessDialog() {
    final registered = context.read<AuthProvider>().lastRegistered;
    final loginAccount = _selectedRole == RegisterRole.elder
        ? _phoneCtrl.text.trim()
        : (_loginUsernameCtrl.text.trim().isNotEmpty
            ? _loginUsernameCtrl.text.trim()
            : _phoneCtrl.text.trim());

    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        backgroundColor: const Color(0xFF0D1C26),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        title: const Text('Ê≥®ÂÜåÊàêÂäü', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('Ë¥¶Âè∑Â∑≤ÂàõÂª∫ÔºåÂèØ‰ª•Áõ¥Êé•ÁôªÂΩï„ÄÇ', style: TextStyle(color: Colors.white70)),
            const SizedBox(height: 16),
            if (registered != null) ...[
              _infoRow('ÂßìÂêç', registered.name),
              _infoRow('ËßíËâ≤', registered.role),
              _infoRow('ÊâãÊú∫Âè∑', registered.phone),
              const SizedBox(height: 8),
            ],
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: const Color(0xFFFF875A).withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: const Color(0xFFFF875A).withOpacity(0.3)),
              ),
              child: Text(
                'ÁôªÂΩïË¥¶Âè∑Ôºö$loginAccount',
                style: const TextStyle(color: Color(0xFFFF875A), fontWeight: FontWeight.bold),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () {
              Navigator.of(ctx).pop();
              Navigator.of(context).pop();
            },
            child: const Text('ÂéªÁôªÂΩï', style: TextStyle(color: Color(0xFFFF875A), fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Widget _infoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        children: [
          Text('$labelÔºö', style: const TextStyle(color: Colors.white54, fontSize: 13)),
          Expanded(child: Text(value, style: const TextStyle(color: Colors.white, fontSize: 13))),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF08161B),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: Colors.white70),
          onPressed: () {
            if (_step == 1) {
              setState(() => _step = 0);
            } else {
              Navigator.of(context).pop();
            }
          },
        ),
        title: Text(
          _step == 0 ? 'ÈÄâÊã©Ê≥®ÂÜåÁ±ªÂûã' : 'Â°´ÂÜôÊ≥®ÂÜå‰ø°ÊÅØ',
          style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
      ),
      body: AnimatedSwitcher(
        duration: const Duration(milliseconds: 250),
        child: _step == 0
            ? _buildRoleStep()
            : _buildFormStep(),
      ),
    );
  }

  Widget _buildRoleStep() {
    return Padding(
      key: const ValueKey('role'),
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('«Î—°‘Òƒ˙µƒ…Ì∑›',
              style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          const Text('≤ªÕ¨…Ì∑›”µ”–≤ªÕ¨µƒπ¶ƒ‹∫Õ ˝æ› ”Ω«',
              style: TextStyle(color: Colors.white54, fontSize: 14)),
          const SizedBox(height: 32),
          ...RegisterRole.values.map(_buildRoleCard),
          const Spacer(),
          ElevatedButton(
            onPressed: () => setState(() => _step = 1),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFFF875A),
              foregroundColor: const Color(0xFF08161B),
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: const Text('œ¬“ª≤Ω', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ),
        ],
      ),
    );
  }

  Widget _buildRoleCard(RegisterRole role) {
    final isSelected = _selectedRole == role;
    return GestureDetector(
      onTap: () => setState(() => _selectedRole = role),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFFFF875A).withOpacity(0.12) : Colors.white.withOpacity(0.04),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? const Color(0xFFFF875A).withOpacity(0.6) : Colors.white.withOpacity(0.08),
            width: isSelected ? 1.5 : 1,
          ),
        ),
        child: Row(
          children: [
            Container(
              width: 44, height: 44,
              decoration: BoxDecoration(
                color: isSelected ? const Color(0xFFFF875A).withOpacity(0.2) : Colors.white.withOpacity(0.06),
                shape: BoxShape.circle,
              ),
              child: Icon(_roleIcon(role), color: isSelected ? const Color(0xFFFF875A) : Colors.white38, size: 22),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(role.label, style: TextStyle(color: isSelected ? Colors.white : Colors.white70, fontWeight: FontWeight.bold, fontSize: 16)),
                  const SizedBox(height: 4),
                  Text(role.description, style: const TextStyle(color: Colors.white38, fontSize: 13)),
                ],
              ),
            ),
            if (isSelected) const Icon(Icons.check_circle, color: Color(0xFFFF875A), size: 20),
          ],
        ),
      ),
    );
  }

  IconData _roleIcon(RegisterRole role) {
    switch (role) {
      case RegisterRole.elder: return Icons.elderly;
      case RegisterRole.family: return Icons.family_restroom;
      case RegisterRole.community: return Icons.business_center;
    }
  }

  Widget _buildFormStep() {
    final authProvider = context.watch<AuthProvider>();
    final isSubmitting = authProvider.registerStatus == RegisterStatus.submitting;
    return SingleChildScrollView(
      key: const ValueKey('form'),
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            decoration: BoxDecoration(
              color: const Color(0xFFFF875A).withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
              border: Border.all(color: const Color(0xFFFF875A).withOpacity(0.3)),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(_roleIcon(_selectedRole), color: const Color(0xFFFF875A), size: 16),
                const SizedBox(width: 8),
                Text("◊¢≤·¿‡–Õ£∫${_selectedRole.label}", style: const TextStyle(color: Color(0xFFFF875A), fontWeight: FontWeight.w600)),
              ],
            ),
          ),
          const SizedBox(height: 24),
          _buildTextField(_nameCtrl, "–’√˚", Icons.person_outline, hint: "«Î ‰»Î’Ê µ–’√˚"),
          const SizedBox(height: 16),
          if (_selectedRole == RegisterRole.elder) ...[
            _buildTextField(_phoneCtrl, " ÷ª˙∫≈£®µ«¬º’À∫≈£©", Icons.phone_outlined, hint: " ÷ª˙∫≈Ω´◊˜Œ™µ«¬º’À∫≈", keyboardType: TextInputType.phone),
            const SizedBox(height: 16),
            _buildTextField(_ageCtrl, "ƒÍ¡‰", Icons.cake_outlined, hint: "«Î ‰»ÎƒÍ¡‰£®50-120£©", keyboardType: TextInputType.number),
            const SizedBox(height: 16),
            _buildTextField(_apartmentCtrl, "∑øº‰∫≈", Icons.home_outlined, hint: "¿˝»Á A-302"),
            const SizedBox(height: 16),
          ] else ...[
            _buildTextField(_phoneCtrl, " ÷ª˙∫≈", Icons.phone_outlined, hint: "«Î ‰»Î ÷ª˙∫≈", keyboardType: TextInputType.phone),
            const SizedBox(height: 16),
            _buildTextField(_loginUsernameCtrl, "µ«¬º’À∫≈£®ø…—°£©", Icons.account_circle_outlined, hint: "¡Ùø’‘Ú“‘ ÷ª˙∫≈◊˜Œ™µ«¬º’À∫≈"),
            const SizedBox(height: 16),
          ],
          if (_selectedRole == RegisterRole.family) ...[
            _buildRelationshipSelector(),
            const SizedBox(height: 16),
          ],
          TextField(
            controller: _passwordCtrl,
            obscureText: _obscurePassword,
            style: const TextStyle(color: Colors.white),
            decoration: InputDecoration(
              labelText: "√‹¬Î",
              labelStyle: const TextStyle(color: Colors.white54),
              hintText: "÷¡…Ÿ 6 Œª",
              hintStyle: const TextStyle(color: Colors.white24),
              filled: true,
              fillColor: Colors.white.withOpacity(0.05),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
              prefixIcon: const Icon(Icons.lock_outline, color: Colors.white54),
              suffixIcon: IconButton(
                icon: Icon(_obscurePassword ? Icons.visibility_off_outlined : Icons.visibility_outlined, color: Colors.white38),
                onPressed: () => setState(() => _obscurePassword = !_obscurePassword),
              ),
            ),
          ),
          if (authProvider.registerStatus == RegisterStatus.error && authProvider.registerError != null) ...[
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.red.withOpacity(0.1),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: Colors.redAccent.withOpacity(0.3)),
              ),
              child: Text(authProvider.registerError!, style: const TextStyle(color: Colors.redAccent, fontSize: 14)),
            ),
          ],
          const SizedBox(height: 32),
          ElevatedButton(
            onPressed: isSubmitting ? null : _submit,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFFF875A),
              foregroundColor: const Color(0xFF08161B),
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: isSubmitting
                ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF08161B)))
                : const Text("ÕÍ≥…◊¢≤·", style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ),
          const SizedBox(height: 16),
          Center(
            child: TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text("“—”–’À∫≈£ø∑µªÿµ«¬º", style: TextStyle(color: Colors.white38)),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTextField(TextEditingController controller, String label, IconData icon, {String? hint, TextInputType keyboardType = TextInputType.text}) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        labelText: label,
        labelStyle: const TextStyle(color: Colors.white54),
        hintText: hint,
        hintStyle: const TextStyle(color: Colors.white24),
        filled: true,
        fillColor: Colors.white.withOpacity(0.05),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
        prefixIcon: Icon(icon, color: Colors.white54),
      ),
    );
  }

  Widget _buildRelationshipSelector() {
    return DropdownButtonFormField<String>(
      value: _relationship,
      dropdownColor: const Color(0xFF0D1C26),
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        labelText: "”Î¿œ»Àµƒπÿœµ",
        labelStyle: const TextStyle(color: Colors.white54),
        filled: true,
        fillColor: Colors.white.withOpacity(0.05),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
        prefixIcon: const Icon(Icons.people_outline, color: Colors.white54),
      ),
      items: _relationships.map((r) => DropdownMenuItem(value: r.$1, child: Text(r.$2))).toList(),
      onChanged: (v) => setState(() => _relationship = v ?? "daughter"),
    );
  }
}
