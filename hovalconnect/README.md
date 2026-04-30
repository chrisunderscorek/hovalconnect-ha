# Hoval Connect

Home Assistant App that installs or updates the bundled Hoval Connect custom integration.

Install the repository in Home Assistant:

```text
https://github.com/chrisunderscorek/hovalconnect-ha
```

Then install and start the **Hoval Connect** app once. It copies the integration to:

```text
/config/custom_components/hovalconnect
```

Restart Home Assistant Core afterwards and add the integration from **Settings > Devices & services**.

During integration setup you can choose **System**, **Deutsch**, or **English** as the Hoval Connect language. This only changes Hoval Connect entity names and program labels; it does not change the global Home Assistant language.

The integration exposes heat output and inverter energy use as `kWh` energy sensors and maps WFA-200 operating status codes to readable German/English status names.
