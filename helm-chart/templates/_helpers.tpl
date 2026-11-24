{{/* Common name helpers. */}}
{{- define "soroscan.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "soroscan.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "soroscan.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "soroscan.labels" -}}
helm.sh/chart: {{ include "soroscan.chart" . }}
app.kubernetes.io/name: {{ include "soroscan.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app: {{ include "soroscan.name" . }}
{{- end }}

{{- define "soroscan.selectorLabels" -}}
app.kubernetes.io/name: {{ include "soroscan.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app: {{ include "soroscan.name" . }}
{{- end }}

{{- define "soroscan.image" -}}
{{- printf "%s:%s" .Values.image.repository .Values.image.tag }}
{{- end }}

{{- define "soroscan.configMapName" -}}
{{- printf "%s-config" (include "soroscan.fullname" .) }}
{{- end }}

{{- define "soroscan.secretName" -}}
{{- if .Values.secrets.existingSecret }}
{{- .Values.secrets.existingSecret }}
{{- else }}
{{- printf "%s-secrets" (include "soroscan.fullname" .) }}
{{- end }}
{{- end }}

{{- define "soroscan.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "soroscan.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
