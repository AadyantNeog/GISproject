<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28" styleCategories="Symbology">
  <renderer-v2 type="graduatedSymbol" attr="exposed_any_km2" graduatedMethod="GraduatedColor">
    <ranges>
      <range lower="0" upper="0.0001" symbol="0" label="0" render="true"/>
      <range lower="0.0001" upper="0.005" symbol="1" label="&lt; 0.5 ha" render="true"/>
      <range lower="0.005" upper="0.01" symbol="2" label="0.5-1 ha" render="true"/>
      <range lower="0.01" upper="0.02" symbol="3" label="1-2 ha" render="true"/>
      <range lower="0.02" upper="1" symbol="4" label="&gt; 2 ha" render="true"/>
    </ranges>
    <symbols>
      <symbol type="fill" name="0" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option type="QString" name="color" value="#f4f2ee"/><Option type="QString" name="outline_style" value="no"/></Option></layer></symbol>
      <symbol type="fill" name="1" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option type="QString" name="color" value="#fdd49e"/><Option type="QString" name="outline_style" value="no"/></Option></layer></symbol>
      <symbol type="fill" name="2" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option type="QString" name="color" value="#fc8d59"/><Option type="QString" name="outline_style" value="no"/></Option></layer></symbol>
      <symbol type="fill" name="3" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option type="QString" name="color" value="#d7301f"/><Option type="QString" name="outline_style" value="no"/></Option></layer></symbol>
      <symbol type="fill" name="4" alpha="1"><layer class="SimpleFill"><Option type="Map"><Option type="QString" name="color" value="#7f0000"/><Option type="QString" name="outline_style" value="no"/></Option></layer></symbol>
    </symbols>
  </renderer-v2>
</qgis>
