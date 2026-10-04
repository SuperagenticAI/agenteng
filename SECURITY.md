# Security

The project is currently an initial 0.1 release. Security fixes target the latest release; older releases have no separate maintenance guarantee. Optional model engines are disabled by default and have not yet undergone live-provider quality or cost evaluation.

Please do not open a public issue containing an exploit, credential, private submission or personal data. Use the repository's [**Security → Report a vulnerability**](https://github.com/SuperagenticAI/agenteng/security/advisories/new) option when private vulnerability reporting is enabled. If it is unavailable, contact [events@agentengineering.world](mailto:events@agentengineering.world) with a short description and ask for a private reporting channel. Do not attach live credentials.

Useful reports describe the affected version, impact and minimal reproduction. Disclosure and response timing should be coordinated with the maintainers; there is no guaranteed response time or bounty program.

The public server exposes catalogue lookups. Operators are responsible for HTTPS, allowed hosts/origins, deployment secrets, infrastructure quotas and updates. Optional inference additionally requires an operator credential, configured provider and explicit engine request. Per-request model limits do not provide a distributed daily spending cap. See [architecture](docs/ARCHITECTURE.md) and [deployment](deploy/README.md).

The optional private intake pilot is disabled by default. It needs an encrypted persistent volume, private directory permissions, participant credential distribution/revocation, an approved privacy notice and retention/backup handling. Participant tokens prove possession, not verified identity. SQLite is not encrypted by this application and must not run on an ephemeral server filesystem. Keep authorization headers and proposal bodies out of infrastructure logs. See [participation deployment requirements](docs/PARTICIPATION.md).

The installer uses HTTPS and verifies a versioned wheel against a checksum from the same release origin. This detects corruption; it is not an independent signature or protection against a compromised release origin. Review the script and download from the official project site.
