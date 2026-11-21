<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.28" styleCategories="Symbology">
  <pipe>
    <rasterrenderer type="paletted" band="1" opacity="1" alphaBand="-1">
      <colorPalette>
        <paletteEntry value="0" color="#ffffff" alpha="0" label="not built-up"/>
        <paletteEntry value="1" color="#8c8c8c" alpha="255" label="built-up &gt; 100 m from flood"/>
        <paletteEntry value="2" color="#fdae61" alpha="255" label="built-up 50-100 m from flood"/>
        <paletteEntry value="3" color="#d7301f" alpha="255" label="built-up &lt;= 50 m from flood"/>
        <paletteEntry value="255" color="#ffffff" alpha="0" label="outside district"/>
      </colorPalette>
    </rasterrenderer>
  </pipe>
</qgis>
